from __future__ import annotations

from collections import defaultdict
from typing import Optional

from ortools.sat.python import cp_model

from app.models.domain import (
    MaintenanceTask,
    MaintenanceBlock,
    BlockWindow,
    Train,
    WhatIfScenario,
    PlanMetrics,
)


class BlockOptimizer:
    """
    OR-Tools CP-SAT based maintenance block optimizer.

    Hard constraints:
      - task can be assigned at most once
      - task/corridor must match the maintenance window
      - task block type must match window block type
      - task must fit before the next scheduled train
      - dependencies must be scheduled first
      - conflicting safety requirements cannot share a block
      - isolation tasks cannot collide
      - same physical location cannot overlap
      - same named resource cannot be used by two simultaneous tasks

    Scheduling model:
      - tasks from DIFFERENT departments can run in parallel
      - tasks from the SAME department are sequential
      - therefore block duration is the maximum departmental workload
    """

    MAX_TASKS = 500
    MAX_WINDOWS = 100

    SOLVER_SECONDS = 30
    NUM_WORKERS = 4

    SAFETY_CONFLICTS = {
        frozenset(("Power Block Required", "Lines Up")),
        frozenset(("Track Isolation", "Power Block Required")),
    }

    def __init__(self):
        self._reset_solver()

    def _reset_solver(self):
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        self.solver.parameters.max_time_in_seconds = (
            self.SOLVER_SECONDS
        )
        self.solver.parameters.num_workers = (
            self.NUM_WORKERS
        )
        self.solver.parameters.log_search_progress = False

    @staticmethod
    def _time_to_minutes(time_str: str) -> int:
        parts = time_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])

    @staticmethod
    def _overlap(
        start_a: int,
        end_a: int,
        start_b: int,
        end_b: int,
    ) -> bool:
        return (
            start_a < end_b
            and start_b < end_a
        )

    def optimize(
        self,
        tasks: list[MaintenanceTask],
        block_windows: list[BlockWindow],
        trains: list[Train],
        scenario: Optional[WhatIfScenario] = None,
        resource_factor: float = 1.0,
    ) -> tuple[
        list[MaintenanceBlock],
        PlanMetrics,
    ]:

        scenario = scenario or WhatIfScenario()

        self._reset_solver()

        # Only pending work is eligible for scheduling.
        task_list = [
            task
            for task in tasks
            if task.status.value == "Pending"
            and task.priority_score > 0
        ]

        task_list = task_list[: self.MAX_TASKS]

        windows = sorted(
            block_windows[: self.MAX_WINDOWS],
            key=lambda window: (
                window.corridor_id,
                window.day_of_week,
                self._time_to_minutes(
                    window.start_time
                ),
            ),
        )

        if not task_list or not windows:
            return (
                [],
                self._calculate_metrics(
                    tasks,
                    [],
                    set(),
                    trains,
                ),
            )

        task_by_id = {
            task.task_id: task
            for task in task_list
        }

        # ---------------------------------------------------------
        # Candidate assignment variables
        # ---------------------------------------------------------

        compatible_windows: dict[
            str,
            list[int],
        ] = defaultdict(list)

        for task in task_list:
            for window_index, window in enumerate(
                windows
            ):

                if not self._task_can_use_window(
                    task,
                    window,
                    scenario,
                ):
                    continue

                safe_duration = (
                    self._window_safe_duration(
                        window,
                        trains,
                        scenario,
                    )
                )

                if (
                    safe_duration
                    >= task.estimated_duration_minutes
                ):
                    compatible_windows[
                        task.task_id
                    ].append(window_index)

        assign: dict[
            tuple[str, int],
            cp_model.IntVar,
        ] = {}

        for task in task_list:
            for window_index in compatible_windows.get(
                task.task_id,
                [],
            ):
                assign[
                    (
                        task.task_id,
                        window_index,
                    )
                ] = self.model.NewBoolVar(
                    f"assign_{task.task_id}_{window_index}"
                )

        # Each task can be scheduled at most once.
        for task in task_list:

            variables = [
                assign[
                    (
                        task.task_id,
                        window_index,
                    )
                ]
                for window_index in compatible_windows.get(
                    task.task_id,
                    [],
                )
            ]

            if variables:
                self.model.Add(
                    sum(variables) <= 1
                )

        # ---------------------------------------------------------
        # Window bookkeeping
        # ---------------------------------------------------------

        window_tasks: dict[
            int,
            list[str],
        ] = defaultdict(list)

        for task in task_list:
            for window_index in compatible_windows.get(
                task.task_id,
                [],
            ):
                window_tasks[
                    window_index
                ].append(task.task_id)

        departments = sorted(
            {
                task.department.value
                for task in task_list
            }
        )

        block_used: dict[
            int,
            cp_model.IntVar,
        ] = {}

        block_duration: dict[
            int,
            cp_model.IntVar,
        ] = {}

        department_load: dict[
            tuple[int, str],
            cp_model.IntVar,
        ] = {}

        multi_dept: dict[
            int,
            cp_model.IntVar,
        ] = {}

        for window_index, window in enumerate(
            windows
        ):

            safe_duration = (
                self._window_safe_duration(
                    window,
                    trains,
                    scenario,
                )
            )

            block_used[
                window_index
            ] = self.model.NewBoolVar(
                f"block_used_{window_index}"
            )

            block_duration[
                window_index
            ] = self.model.NewIntVar(
                0,
                max(0, safe_duration),
                f"block_duration_{window_index}",
            )

            task_variables = [
                assign[
                    (
                        task_id,
                        window_index,
                    )
                ]
                for task_id in window_tasks.get(
                    window_index,
                    [],
                )
            ]

            if task_variables:
                self.model.AddMaxEquality(
                    block_used[
                        window_index
                    ],
                    task_variables,
                )
            else:
                self.model.Add(
                    block_used[
                        window_index
                    ]
                    == 0
                )

            department_load_vars = []

            for department in departments:

                load = self.model.NewIntVar(
                    0,
                    max(0, safe_duration),
                    (
                        f"load_"
                        f"{window_index}_"
                        f"{department}"
                    ),
                )

                department_load[
                    (
                        window_index,
                        department,
                    )
                ] = load

                terms = []

                for task_id in window_tasks.get(
                    window_index,
                    [],
                ):

                    task = task_by_id[
                        task_id
                    ]

                    if (
                        task.department.value
                        == department
                    ):
                        terms.append(
                            task.estimated_duration_minutes
                            * assign[
                                (
                                    task_id,
                                    window_index,
                                )
                            ]
                        )

                self.model.Add(
                    load
                    == (
                        sum(terms)
                        if terms
                        else 0
                    )
                )

                self.model.Add(
                    load
                    <= safe_duration
                    * block_used[
                        window_index
                    ]
                )

                department_load_vars.append(
                    load
                )

            if department_load_vars:

                self.model.AddMaxEquality(
                    block_duration[
                        window_index
                    ],
                    department_load_vars,
                )

            else:

                self.model.Add(
                    block_duration[
                        window_index
                    ]
                    == 0
                )

            # -------------------------------------------------
            # Multi-department coordination indicator
            # -------------------------------------------------

            department_presence = []

            for department in departments:

                presence = self.model.NewBoolVar(
                    (
                        f"dept_present_"
                        f"{window_index}_"
                        f"{department}"
                    )
                )

                load = department_load[
                    (
                        window_index,
                        department,
                    )
                ]

                self.model.Add(
                    load > 0
                ).OnlyEnforceIf(
                    presence
                )

                self.model.Add(
                    load == 0
                ).OnlyEnforceIf(
                    presence.Not()
                )

                department_presence.append(
                    presence
                )

            multi_dept[
                window_index
            ] = self.model.NewBoolVar(
                f"multi_dept_{window_index}"
            )

            # multi_dept = 1 requires at least
            # two departments.
            self.model.Add(
                sum(department_presence)
                >=
                2 * multi_dept[
                    window_index
                ]
            )

            # If multi_dept is true, at least
            # two departments must be present.
            if department_presence:

                for presence in department_presence:

                    self.model.AddImplication(
                        multi_dept[
                            window_index
                        ],
                        presence,
                    )

        # ---------------------------------------------------------
        # Dependency constraints
        # ---------------------------------------------------------

        window_rank = {
            index: (
                window.day_of_week
                * 1440
                + self._time_to_minutes(
                    window.start_time
                )
            )
            for index, window in enumerate(
                windows
            )
        }

        for task in task_list:

            task_variables = [
                assign[
                    (
                        task.task_id,
                        window_index,
                    )
                ]
                for window_index in compatible_windows.get(
                    task.task_id,
                    [],
                )
            ]

            if not task_variables:
                continue

            for dependency_id in task.dependencies:

                # Dependency must exist in the pending
                # task population.
                if dependency_id not in task_by_id:

                    for variable in task_variables:
                        self.model.Add(
                            variable == 0
                        )

                    continue

                dependency_variables = [
                    assign[
                        (
                            dependency_id,
                            window_index,
                        )
                    ]
                    for window_index in compatible_windows.get(
                        dependency_id,
                        [],
                    )
                ]

                if not dependency_variables:

                    for variable in task_variables:
                        self.model.Add(
                            variable == 0
                        )

                    continue

                # If task is scheduled, dependency
                # must also be scheduled.
                self.model.Add(
                    sum(dependency_variables)
                    >=
                    sum(task_variables)
                )

                # Dependency must be earlier.
                for task_window_index in compatible_windows.get(
                    task.task_id,
                    [],
                ):

                    task_variable = assign[
                        (
                            task.task_id,
                            task_window_index,
                        )
                    ]

                    earlier_dependencies = [
                        assign[
                            (
                                dependency_id,
                                dependency_window_index,
                            )
                        ]
                        for dependency_window_index in compatible_windows.get(
                            dependency_id,
                            [],
                        )
                        if (
                            window_rank[
                                dependency_window_index
                            ]
                            <
                            window_rank[
                                task_window_index
                            ]
                        )
                    ]

                    if earlier_dependencies:

                        self.model.Add(
                            sum(
                                earlier_dependencies
                            )
                            >=
                            task_variable
                        )

                    else:

                        self.model.Add(
                            task_variable == 0
                        )

        # ---------------------------------------------------------
        # Same-block hard conflicts
        # ---------------------------------------------------------

        for window_index, task_ids in (
            window_tasks.items()
        ):

            for first_index in range(
                len(task_ids)
            ):

                first_task = task_by_id[
                    task_ids[first_index]
                ]

                for second_index in range(
                    first_index + 1,
                    len(task_ids),
                ):

                    second_task = task_by_id[
                        task_ids[second_index]
                    ]

                    first_variable = assign[
                        (
                            first_task.task_id,
                            window_index,
                        )
                    ]

                    second_variable = assign[
                        (
                            second_task.task_id,
                            window_index,
                        )
                    ]

                    if self._tasks_conflict(
                        first_task,
                        second_task,
                    ):
                        self.model.Add(
                            first_variable
                            + second_variable
                            <= 1
                        )

        # ---------------------------------------------------------
        # Objective
        # ---------------------------------------------------------

        objective_terms = []

        for task in task_list:

            # Priority contribution.
            priority_value = int(
                round(
                    task.priority_score * 10
                )
            )

            # Strong bonus for critical work.
            critical_bonus = (
                500
                if task.priority_score >= 70
                else 0
            )

            task_value = (
                priority_value
                + critical_bonus
            )

            for window_index in compatible_windows.get(
                task.task_id,
                [],
            ):

                objective_terms.append(
                    (
                        task_value,
                        assign[
                            (
                                task.task_id,
                                window_index,
                            )
                        ],
                    )
                )

        # Strong explicit incentive to coordinate.
        for window_index in multi_dept:

            objective_terms.append(
                (
                    1500,
                    multi_dept[
                        window_index
                    ],
                )
            )

        # Encourage useful utilization,
        # discourage too many blocks.
        for window_index, window in enumerate(
            windows
        ):

            safe_duration = (
                self._window_safe_duration(
                    window,
                    trains,
                    scenario,
                )
            )

            if safe_duration <= 0:
                continue

            objective_terms.append(
                (
                    2,
                    block_duration[
                        window_index
                    ],
                )
            )

            objective_terms.append(
                (
                    -250,
                    block_used[
                        window_index
                    ],
                )
            )

        # Prefer earlier windows slightly.
        max_rank = max(
            window_rank.values(),
            default=0,
        )

        for task in task_list:

            for window_index in compatible_windows.get(
                task.task_id,
                [],
            ):

                early_bonus = max(
                    0,
                    max_rank
                    - window_rank[
                        window_index
                    ],
                )

                objective_terms.append(
                    (
                        early_bonus // 60,
                        assign[
                            (
                                task.task_id,
                                window_index,
                            )
                        ],
                    )
                )

        if objective_terms:
            self.model.Maximize(
                sum(
                    weight * variable
                    for weight, variable
                    in objective_terms
                )
            )

        # ---------------------------------------------------------
        # Solve
        # ---------------------------------------------------------

        status = self.solver.Solve(
            self.model
        )

        if status not in (
            cp_model.OPTIMAL,
            cp_model.FEASIBLE,
        ):
            return (
                [],
                self._calculate_metrics(
                    tasks,
                    [],
                    set(),
                    trains,
                ),
            )

        # ---------------------------------------------------------
        # Convert solution into MaintenanceBlocks
        # ---------------------------------------------------------

        selected_by_window: dict[
            int,
            list[MaintenanceTask],
        ] = defaultdict(list)

        assigned_ids: set[str] = set()

        for task in task_list:

            for window_index in compatible_windows.get(
                task.task_id,
                [],
            ):

                variable = assign[
                    (
                        task.task_id,
                        window_index,
                    )
                ]

                if self.solver.Value(
                    variable
                ):

                    selected_by_window[
                        window_index
                    ].append(task)

                    assigned_ids.add(
                        task.task_id
                    )

                    break

        blocks = []

        for window_index in sorted(
            selected_by_window
        ):

            selected_tasks = (
                selected_by_window[
                    window_index
                ]
            )

            if not selected_tasks:
                continue

            duration = self.solver.Value(
                block_duration[
                    window_index
                ]
            )

            block = self._create_block(
                windows[
                    window_index
                ],
                selected_tasks,
                duration,
            )

            blocks.append(block)

        metrics = self._calculate_metrics(
            tasks,
            blocks,
            assigned_ids,
            trains,
        )

        return blocks, metrics

    # ============================================================
    # Candidate validation
    # ============================================================

    def _task_can_use_window(
        self,
        task: MaintenanceTask,
        window: BlockWindow,
        scenario: WhatIfScenario,
    ) -> bool:

        if (
            task.corridor_id
            != window.corridor_id
        ):
            return False

        if (
            task.required_block_type
            != window.block_type
        ):
            return False

        # Scenario restrictions are supplied
        # as corridor IDs in the current project.
        if scenario.corridor_restrictions:

            if (
                task.corridor_id
                in scenario.corridor_restrictions
            ):
                return False

        window_duration = (
            self._window_duration(
                window,
                scenario,
            )
        )

        return (
            window_duration
            >= task.estimated_duration_minutes
        )

    def _window_duration(
        self,
        window: BlockWindow,
        scenario: WhatIfScenario,
    ) -> int:

        duration = max(
            0,
            self._time_to_minutes(
                window.end_time
            )
            - self._time_to_minutes(
                window.start_time
            ),
        )

        if (
            scenario.block_duration_override
            is not None
        ):
            duration = min(
                duration,
                max(
                    0,
                    int(
                        scenario.block_duration_override
                    ),
                ),
            )

        return duration

    def _window_safe_duration(
        self,
        window: BlockWindow,
        trains: list[Train],
        scenario: WhatIfScenario,
    ) -> int:
        """
        Calculate usable time from the window start.

        Because the current train table does not contain
        a day-of-week/date field, train movements are treated
        as recurring daily movements.

        Example:

            maintenance window = 10:00-12:00
            train             = 11:15

        Usable maintenance time = 75 minutes.

        This is much better than simply rejecting the entire
        10:00-12:00 window.
        """

        window_start = (
            self._time_to_minutes(
                window.start_time
            )
        )

        window_end = (
            self._time_to_minutes(
                window.end_time
            )
        )

        duration = max(
            0,
            window_end
            - window_start,
        )

        if (
            scenario.block_duration_override
            is not None
        ):
            duration = min(
                duration,
                max(
                    0,
                    int(
                        scenario.block_duration_override
                    ),
                ),
            )

        # Find the first train after the
        # declared maintenance start.
        next_train = min(
            (
                self._time_to_minutes(
                    train.scheduled_time
                )
                for train in trains
                if (
                    train.corridor_id
                    == window.corridor_id
                    and
                    window_start
                    <= self._time_to_minutes(
                        train.scheduled_time
                    )
                    < window_end
                )
            ),
            default=None,
        )

        if next_train is not None:

            duration = min(
                duration,
                max(
                    0,
                    next_train
                    - window_start,
                ),
            )

        # Apply scenario resource availability.
        #
        # Example:
        #   -20 means 20% fewer available resources.
        resource_factor = 1.0

        if (
            scenario.resource_availability_change
            is not None
        ):
            resource_factor = max(
                0.1,
                1.0
                + (
                    scenario.resource_availability_change
                    / 100.0
                ),
            )

        duration = min(
            duration,
            int(
                duration
                * resource_factor
            ),
        )

        return duration

    # ============================================================
    # Task conflict logic
    # ============================================================

    def _tasks_conflict(
        self,
        first: MaintenanceTask,
        second: MaintenanceTask,
    ) -> bool:

        # Same physical location is the best
        # track-occupancy proxy available in
        # the current schema.
        if (
            first.location
            and second.location
            and first.location
            == second.location
        ):
            return True

        # At most one isolation-required
        # activity can execute in a block.
        if (
            first.isolation_required
            and second.isolation_required
        ):
            return True

        first_safety = {
            value.value
            if hasattr(value, "value")
            else value
            for value in first.safety_requirements
        }

        second_safety = {
            value.value
            if hasattr(value, "value")
            else value
            for value in second.safety_requirements
        }

        # Explicit safety conflict matrix.
        for first_requirement in first_safety:

            for second_requirement in second_safety:

                if (
                    frozenset(
                        (
                            first_requirement,
                            second_requirement,
                        )
                    )
                    in self.SAFETY_CONFLICTS
                ):
                    return True

        # Isolation vs live-line requirement.
        if first.isolation_required:

            if (
                "Lines Up"
                in second_safety
            ):
                return True

        if second.isolation_required:

            if (
                "Lines Up"
                in first_safety
            ):
                return True

        # Current schema has no resource quantities.
        # Therefore identical named resources are
        # treated as mutually exclusive.
        if (
            set(first.required_resources)
            &
            set(second.required_resources)
        ):
            return True

        return False

    # ============================================================
    # Block construction
    # ============================================================

    def _create_block(
        self,
        window: BlockWindow,
        tasks: list[MaintenanceTask],
        duration_minutes: int,
    ) -> MaintenanceBlock:

        start_minutes = (
            self._time_to_minutes(
                window.start_time
            )
        )

        end_minutes = (
            start_minutes
            + max(
                0,
                duration_minutes,
            )
        )

        window_duration = max(
            1,
            self._time_to_minutes(
                window.end_time
            )
            - start_minutes,
        )

        utilization = min(
            100.0,
            (
                duration_minutes
                / window_duration
                * 100.0
            ),
        )

        departments = list(
            dict.fromkeys(
                task.department
                for task in tasks
            )
        )

        average_train_impact = (
            sum(
                task.train_impact
                for task in tasks
            )
            / len(tasks)
            if tasks
            else 0.0
        )

        department_load = defaultdict(int)

        for task in tasks:
            department_load[
                task.department.value
            ] += (
                task.estimated_duration_minutes
            )

        department_text = " + ".join(
            department.value
            for department in departments
        )

        task_text = ", ".join(
            task.task_id
            for task in tasks[:4]
        )

        if len(tasks) > 4:
            task_text += (
                f" (+{len(tasks) - 4} more)"
            )

        explanation = (
            f"Coordinated {department_text} work "
            f"in the declared "
            f"{window.block_type.value} window. "
            f"Tasks: {task_text}. "
            f"Parallel block duration: "
            f"{duration_minutes} min; "
            f"utilization: "
            f"{utilization:.0f}%."
        )

        return MaintenanceBlock(
            block_id=(
                f"BLK-"
                f"{window.corridor_id}-"
                f"{window.window_id}"
            ),
            corridor_id=window.corridor_id,
            start_time=window.start_time,
            end_time=(
                f"{end_minutes // 60:02d}:"
                f"{end_minutes % 60:02d}"
            ),
            duration_minutes=duration_minutes,
            block_type=window.block_type,
            assigned_tasks=[
                task.task_id
                for task in tasks
            ],
            departments=departments,
            utilization=round(
                utilization,
                1,
            ),
            train_impact=round(
                average_train_impact,
                1,
            ),
            status="Proposed",
            explanation=explanation,
        )

    # ============================================================
    # Metrics
    # ============================================================

    def _calculate_metrics(
        self,
        tasks: list[MaintenanceTask],
        blocks: list[MaintenanceBlock],
        assigned_ids: set[str],
        trains: list[Train],
    ) -> PlanMetrics:

        total_tasks = len(tasks)
        assigned_count = len(
            assigned_ids
        )

        critical_tasks = [
            task
            for task in tasks
            if task.priority_score >= 70
        ]

        critical_assigned = sum(
            task.task_id in assigned_ids
            for task in critical_tasks
        )

        multi_department_blocks = sum(
            len(block.departments) > 1
            for block in blocks
        )

        average_utilization = (
            sum(
                block.utilization
                for block in blocks
            )
            / len(blocks)
            if blocks
            else 0.0
        )

        train_conflicts = 0

        for block in blocks:

            block_start = (
                self._time_to_minutes(
                    block.start_time
                )
            )

            block_end = (
                self._time_to_minutes(
                    block.end_time
                )
            )

            train_conflicts += sum(
                (
                    train.corridor_id
                    == block.corridor_id
                    and
                    block_start
                    <= self._time_to_minutes(
                        train.scheduled_time
                    )
                    < block_end
                )
                for train in trains
            )

        total_downtime = sum(
            block.duration_minutes
            for block in blocks
        )

        total_week_minutes = (
            7 * 24 * 60
        )

        asset_availability = round(
            max(
                0.0,
                (
                    total_week_minutes
                    - total_downtime
                )
                / total_week_minutes
                * 100.0,
            ),
            1,
        )

        return PlanMetrics(
            asset_availability=asset_availability,
            maintenance_backlog=(
                total_tasks
                - assigned_count
            ),
            planned_blocks=len(blocks),
            train_conflicts=train_conflicts,
            train_disruption_minutes=(
                train_conflicts * 15
            ),
            block_utilization=round(
                average_utilization,
                1,
            ),
            multi_dept_blocks=(
                multi_department_blocks
            ),
            critical_tasks_completed=(
                critical_assigned
            ),
            total_tasks=total_tasks,
            separate_blocks_avoided=max(
                0,
                assigned_count
                - len(blocks),
            ),
            total_downtime_minutes=(
                total_downtime
            ),
        )