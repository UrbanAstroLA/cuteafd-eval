class RateLimitError(Exception):
    pass


class ConfigError(RateLimitError):
    pass


class RateLimited(RateLimitError):
    def __init__(self, policy, retry_after):
        super().__init__(f"rate limited by {policy!r}; retry after {retry_after}s")
        self.policy = policy
        self.retry_after = retry_after
