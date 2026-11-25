class ProviderError(RuntimeError):
    retryable = False


class ProviderConfigurationError(ProviderError):
    pass


class ProviderAuthenticationError(ProviderError):
    pass


class ProviderNotFoundError(ProviderError):
    pass


class ProviderRateLimitError(ProviderError):
    retryable = True


class ProviderServerError(ProviderError):
    retryable = True


class ProviderTransportError(ProviderError):
    retryable = True


class ProviderResponseError(ProviderError):
    pass
