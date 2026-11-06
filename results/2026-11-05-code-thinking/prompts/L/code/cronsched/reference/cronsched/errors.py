class CronError(Exception):
    pass


class CronSyntaxError(CronError):
    def __init__(self, message, field=None):
        self.field = field
        super().__init__(message if field is None else f"{field}: {message}")


class SchedulerError(CronError):
    pass
