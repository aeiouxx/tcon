from enum import IntEnum

# extracted from aimsun C++ code


class AimsunStatus(IntEnum):
    OK = 0

    # Incident-specific errors
    INCIDENT_WRONG_INITIME = -8001
    INCIDENT_WRONG_POSITION = -8002
    INCIDENT_UNKNOWN_LANE = -8003
    INCIDENT_UNKNOWN_SECTION = -8004
    INCIDENT_NOT_PRESENT = -8005
    INCIDENT_WRONG_LENGTH = -8006
    INCIDENT_WRONG_DURATION = -8007

    # Network info errors
    INF_NET_GET_MEM = -5001
    INF_UNKNOWN_ID = -5002
    INF_UNKNOWN_TURNING = -5003
    INF_UNKNOWN_FROM_SECTION = -5004
    INF_UNKNOWN_TO_SECTION = -5005
    INF_NO_PATH = -5006

    # Fallbacks
    UNKNOWN_ERROR = -9999
    API_FAILURE = -1

    @classmethod
    def from_code(cls, code: int) -> "AimsunStatus":
        try:
            return AimsunStatus(code)
        except ValueError:
            return cls.UNKNOWN_ERROR if code < 0 else cls.OK
