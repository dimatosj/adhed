from taskstore.models.enums import StateType

VALID_TRANSITIONS: dict[StateType, set[StateType]] = {
    StateType.TRIAGE: {StateType.BACKLOG, StateType.UNSTARTED, StateType.CANCELED},
    StateType.BACKLOG: {StateType.UNSTARTED, StateType.TRIAGE, StateType.CANCELED},
    StateType.UNSTARTED: {StateType.STARTED, StateType.BACKLOG, StateType.CANCELED},
    StateType.STARTED: {StateType.COMPLETED, StateType.UNSTARTED, StateType.BACKLOG, StateType.CANCELED},
    StateType.COMPLETED: {StateType.UNSTARTED},
    StateType.CANCELED: {StateType.BACKLOG},
}


def is_valid_transition(from_type: StateType, to_type: StateType) -> bool:
    if from_type == to_type:
        return True  # Same category always OK
    return to_type in VALID_TRANSITIONS.get(from_type, set())
