"""
Resilience patterns for DuckLake application.

Provides circuit breaker, retry logic, rate limiting, and other patterns
to improve system reliability and fault tolerance.
"""

import asyncio
import time
import random
from typing import Any, Callable, Optional, Dict, TypeVar, Generic, Union, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from contextlib import asynccontextmanager, contextmanager
from loguru import logger

from .exceptions import (
    TimeoutError, 
    RateLimitExceededError, 
    ResourceException,
    DuckLakeException
)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, requests rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5              # Failures before opening
    recovery_timeout: float = 60.0          # Seconds before attempting recovery
    success_threshold: int = 3              # Successes needed to close from half-open
    timeout: float = 30.0                   # Request timeout in seconds
    expected_exceptions: tuple = (Exception,)  # Exceptions that count as failures


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker pattern implementation.
    
    Prevents cascading failures by monitoring operation success/failure rates
    and temporarily stopping requests when failures exceed threshold.
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            self.stats.total_requests += 1
            
            # Check if circuit is open
            if self.stats.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info("Circuit breaker attempting reset", circuit=self.name)
                    self.stats.state = CircuitState.HALF_OPEN
                    self.stats.success_count = 0
                else:
                    logger.warning("Circuit breaker is open, rejecting request", circuit=self.name)
                    raise ResourceException(
                        f"Circuit breaker '{self.name}' is open",
                        error_code="CIRCUIT_BREAKER_OPEN",
                        context={
                            "circuit_name": self.name,
                            "state": self.stats.state.value,
                            "failure_count": self.stats.failure_count
                        }
                    )
        
        # Execute the function
        try:
            # Apply timeout
            result = await asyncio.wait_for(func(), timeout=self.config.timeout)
            await self._record_success()
            return result
        
        except asyncio.TimeoutError:
            timeout_error = TimeoutError(f"Circuit breaker {self.name}", self.config.timeout)
            await self._record_failure(timeout_error)
            raise timeout_error
        
        except self.config.expected_exceptions as e:
            await self._record_failure(e)
            raise
        
        except Exception as e:
            # Unexpected exceptions don't count as circuit breaker failures
            logger.error("Unexpected error in circuit breaker", circuit=self.name, error=str(e))
            raise
    
    async def _record_success(self) -> None:
        """Record a successful operation."""
        async with self._lock:
            self.stats.total_successes += 1
            
            if self.stats.state == CircuitState.HALF_OPEN:
                self.stats.success_count += 1
                logger.debug("Circuit breaker recorded success", 
                           circuit=self.name, 
                           success_count=self.stats.success_count)
                
                if self.stats.success_count >= self.config.success_threshold:
                    self.stats.state = CircuitState.CLOSED
                    self.stats.failure_count = 0
                    logger.info("Circuit breaker closed after successful recovery", circuit=self.name)
            
            elif self.stats.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.stats.failure_count = 0
    
    async def _record_failure(self, error: Exception) -> None:
        """Record a failed operation."""
        async with self._lock:
            self.stats.total_failures += 1
            self.stats.failure_count += 1
            self.stats.last_failure_time = datetime.now()
            
            logger.warning("Circuit breaker recorded failure", 
                         circuit=self.name, 
                         failure_count=self.stats.failure_count,
                         error=str(error))
            
            if (self.stats.state in [CircuitState.CLOSED, CircuitState.HALF_OPEN] and 
                self.stats.failure_count >= self.config.failure_threshold):
                
                self.stats.state = CircuitState.OPEN
                logger.error("Circuit breaker opened due to failures", 
                           circuit=self.name,
                           failure_count=self.stats.failure_count,
                           threshold=self.config.failure_threshold)
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset."""
        if not self.stats.last_failure_time:
            return True
        
        time_since_failure = datetime.now() - self.stats.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.stats.state.value,
            "failure_count": self.stats.failure_count,
            "success_count": self.stats.success_count,
            "total_requests": self.stats.total_requests,
            "total_failures": self.stats.total_failures,
            "total_successes": self.stats.total_successes,
            "success_rate": (
                self.stats.total_successes / self.stats.total_requests 
                if self.stats.total_requests > 0 else 0.0
            ),
            "last_failure": self.stats.last_failure_time.isoformat() if self.stats.last_failure_time else None
        }


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)


class RetryableOperation:
    """
    Retry logic with exponential backoff and jitter.
    
    Automatically retries failed operations with configurable delays
    and exception filtering.
    """
    
    def __init__(self, name: str, config: Optional[RetryConfig] = None):
        self.name = name
        self.config = config or RetryConfig()
    
    async def execute(self, func: Callable[[], Awaitable[T]]) -> T:
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug("Executing retryable operation", 
                           operation=self.name, 
                           attempt=attempt,
                           max_attempts=self.config.max_attempts)
                
                result = await func()
                
                if attempt > 1:
                    logger.info("Retryable operation succeeded after retry", 
                              operation=self.name, 
                              attempt=attempt)
                
                return result
            
            except self.config.retryable_exceptions as e:
                last_exception = e
                
                if attempt == self.config.max_attempts:
                    logger.error("Retryable operation failed after all attempts", 
                               operation=self.name, 
                               attempts=attempt,
                               error=str(e))
                    break
                
                delay = self._calculate_delay(attempt)
                logger.warning("Retryable operation failed, retrying", 
                             operation=self.name, 
                             attempt=attempt,
                             delay=delay,
                             error=str(e))
                
                await asyncio.sleep(delay)
            
            except Exception as e:
                # Non-retryable exception
                logger.error("Non-retryable exception in retryable operation", 
                           operation=self.name, 
                           attempt=attempt,
                           error=str(e))
                raise
        
        # All attempts failed
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for next retry attempt."""
        delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))
        delay = min(delay, self.config.max_delay)
        
        if self.config.jitter:
            # Add random jitter to prevent thundering herd
            jitter = random.uniform(0, delay * 0.1)
            delay += jitter
        
        return delay


@dataclass
class RateLimiterConfig:
    """Configuration for rate limiter."""
    max_requests: int = 100
    window_seconds: int = 60
    burst_size: Optional[int] = None  # Allow short bursts


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter implementation.
    
    Allows controlled request rates with support for burst traffic.
    """
    
    def __init__(self, name: str, config: RateLimiterConfig):
        self.name = name
        self.config = config
        self.burst_size = config.burst_size or config.max_requests
        self.tokens = float(self.burst_size)
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens_needed: int = 1) -> None:
        """Acquire tokens from the bucket."""
        async with self._lock:
            now = time.time()
            
            # Refill tokens based on elapsed time
            elapsed = now - self.last_refill
            tokens_to_add = elapsed * (self.config.max_requests / self.config.window_seconds)
            self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
            self.last_refill = now
            
            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                logger.debug("Rate limiter granted tokens", 
                           rate_limiter=self.name, 
                           tokens_used=tokens_needed,
                           tokens_remaining=self.tokens)
            else:
                current_rate = self.config.max_requests / self.config.window_seconds
                raise RateLimitExceededError(
                    operation=self.name,
                    current_rate=current_rate,
                    limit=current_rate,
                    window_seconds=self.config.window_seconds
                )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "name": self.name,
            "tokens_available": self.tokens,
            "max_tokens": self.burst_size,
            "refill_rate": self.config.max_requests / self.config.window_seconds,
            "window_seconds": self.config.window_seconds
        }


class ResilienceManager:
    """
    Central manager for resilience patterns.
    
    Provides a unified interface for circuit breakers, retry logic,
    and rate limiting across the application.
    """
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.rate_limiters: Dict[str, TokenBucketRateLimiter] = {}
        self.retry_configs: Dict[str, RetryConfig] = {}
    
    def get_circuit_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name, config)
        return self.circuit_breakers[name]
    
    def get_rate_limiter(self, name: str, config: RateLimiterConfig) -> TokenBucketRateLimiter:
        """Get or create a rate limiter."""
        if name not in self.rate_limiters:
            self.rate_limiters[name] = TokenBucketRateLimiter(name, config)
        return self.rate_limiters[name]
    
    def get_retry_operation(self, name: str, config: Optional[RetryConfig] = None) -> RetryableOperation:
        """Get a retry operation."""
        return RetryableOperation(name, config)
    
    async def resilient_call(
        self,
        func: Callable[[], Awaitable[T]],
        operation_name: str,
        circuit_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        rate_limit_config: Optional[RateLimiterConfig] = None
    ) -> T:
        """Execute function with full resilience patterns."""
        
        # Apply rate limiting
        if rate_limit_config:
            rate_limiter = self.get_rate_limiter(operation_name, rate_limit_config)
            await rate_limiter.acquire()
        
        # Apply circuit breaker and retry
        circuit_breaker = self.get_circuit_breaker(operation_name, circuit_config)
        retry_operation = self.get_retry_operation(operation_name, retry_config)
        
        async def protected_func():
            return await circuit_breaker.call(func)
        
        return await retry_operation.execute(protected_func)
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all resilience components."""
        return {
            "circuit_breakers": {
                name: cb.get_stats() 
                for name, cb in self.circuit_breakers.items()
            },
            "rate_limiters": {
                name: rl.get_stats() 
                for name, rl in self.rate_limiters.items()
            }
        }


# Global resilience manager
resilience_manager = ResilienceManager()


# Decorators for easy usage
def circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None):
    """Decorator to add circuit breaker protection to async functions."""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            cb = resilience_manager.get_circuit_breaker(name, config)
            return await cb.call(lambda: func(*args, **kwargs))
        return wrapper
    return decorator


def retryable(name: str, config: Optional[RetryConfig] = None):
    """Decorator to add retry logic to async functions."""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            retry_op = resilience_manager.get_retry_operation(name, config)
            return await retry_op.execute(lambda: func(*args, **kwargs))
        return wrapper
    return decorator


def rate_limited(name: str, config: RateLimiterConfig):
    """Decorator to add rate limiting to async functions."""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            rate_limiter = resilience_manager.get_rate_limiter(name, config)
            await rate_limiter.acquire()
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def resilient(
    operation_name: str,
    circuit_config: Optional[CircuitBreakerConfig] = None,
    retry_config: Optional[RetryConfig] = None,
    rate_limit_config: Optional[RateLimiterConfig] = None
):
    """Decorator to add full resilience patterns to async functions."""
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await resilience_manager.resilient_call(
                lambda: func(*args, **kwargs),
                operation_name,
                circuit_config,
                retry_config,
                rate_limit_config
            )
        return wrapper
    return decorator 