---
applyTo: '**'
---
# Coding Standards and Best Practices

This document defines the coding standards and best practices for the entire project.
These rules apply to all code, regardless of specific features or migrations.

---

## Core Development Principles

**1. INCREMENTAL CHANGES ONLY**
- Never refactor multiple subsystems simultaneously
- Each change must be isolated to ONE component or layer
- Complete and validate one change before starting the next
- Keep the system functional at ALL times
- Commit working code frequently (after each validated change)

**2. ALWAYS CHECK FOR ERRORS AFTER CHANGES - CRITICAL RULE**
- ✅ ALWAYS run `get_errors()` after making ANY code changes
- ✅ ALWAYS verify changes didn't introduce type errors or compile errors
- ✅ Check both the files you changed AND related files that import them
- ✅ Fix all errors before proceeding to next task
- ❌ NEVER assume changes are correct without verification
- **Why:** Prevents cascading errors and catches issues early

**3. ALWAYS RUN TESTS — ASK FIRST - CRITICAL RULE**
- ✅ Running tests is MANDATORY at the end of every feature and after any non-trivial change
- ✅ ALWAYS ask the user before running the test suite (e.g. "Ready to run tests — shall I proceed?")
- ✅ Once the user confirms (explicitly or implicitly by asking you to run them), run them immediately
- ✅ Report results clearly: pass count, failure details, and any relevant output
- ✅ Fix any failing tests before declaring the feature done
- ❌ NEVER skip running tests because "the code looks correct"
- ❌ NEVER declare a feature complete without test results
- ❌ NEVER start browsers or require user credentials on their behalf without asking
- **Why:** Tests are the only objective proof of correctness. Skipping them is how bugs ship.
- **When tests can't run automatically** (e.g. require real credentials, external services, or a specific device):
  1. State clearly why they cannot be run
  2. Explain what the test validates and what success looks like
  3. Ask the user to run them and report the output

**4. ALWAYS VERIFY LIBRARY API BEHAVIOR (CRITICAL)**
- Do NOT trust documentation alone - test API calls in terminal first
- Use `dir()`, `type()`, `help()` to inspect actual module structure
- Write small test scripts to verify parameter names, return types, calling conventions
- Document discovered API behavior in code comments
- When API differs from docs, trust your tests and update code accordingly
- Add type hints based on ACTUAL behavior, not documentation
- Use `# type: ignore` only when absolutely necessary with explanation

---

## Type Safety Standards

**5. TYPE SAFETY IS MANDATORY**
- ALL code MUST have complete type hints
- Use `from typing import Optional, List, Dict, Any, Callable, Union, Tuple`
- Function signatures must specify parameter types and return types
- Use `Optional[T]` for nullable returns, never implicit None
- Use Protocol or ABC for interface definitions
- Enable strict mypy checking for new code
- No `Any` types unless absolutely necessary (document why if used)

**6. FUNCTION SIGNATURES**
All functions must be typed like this:
```python
from typing import Optional, List, Dict, Any

async def login(
    self, 
    username: str, 
    password: str,
    totp_secret: Optional[str] = None
) -> bool:
    """Login with credentials."""
    pass

async def capture_response(
    self,
    request_id: str,
    url: str
) -> Optional[Dict[str, Any]]:
    """Capture and parse response."""
    pass
```

**7. CLASS ATTRIBUTES**
Type all class attributes:
```python
from typing import Optional, List

class DataProcessor:
    """Process data with configuration."""
    
    def __init__(self, config: ProcessorConfig) -> None:
        self.config: ProcessorConfig = config
        self.cache: Optional[Dict[str, Any]] = None
        self.results: List[Dict[str, Any]] = []
        self._timeout_ms: int = 30000
```

**8. COMPLEX TYPES**
Use TypedDict for structured data:
```python
from typing import TypedDict, List

class ProcessedRecord(TypedDict):
    record_id: str
    data_type: str
    fields: Dict[str, Any]
    metadata: Optional[Dict[str, str]]

class ExecutionResult(TypedDict):
    status: str
    records: List[ProcessedRecord]
    error_count: int
```

**9. GENERIC TYPES**
Use generics for reusable components:
```python
from typing import TypeVar, Generic, Callable, Awaitable

T = TypeVar('T')

class DataHandler(Generic[T]):
    """Generic data handler."""
    
    def __init__(self, processor: Callable[[Dict[str, Any]], T]) -> None:
        self.processor = processor
    
    async def process(self, raw_data: Dict[str, Any]) -> T:
        return self.processor(raw_data)
```

---

## Code Quality Standards

**10. DOCSTRINGS REQUIRED**
Every function/class must have docstring:
```python
async def wait_for_element(
    self,
    selector: str,
    state: str = "visible",
    timeout: int = 30000
) -> bool:
    """Wait for element to reach desired state.
    
    Args:
        selector: CSS or XPath selector for target element
        state: Desired element state to wait for (visible, hidden, attached)
        timeout: Maximum wait time in milliseconds
        
    Returns:
        True if element reached state, False if timeout
        
    Raises:
        TimeoutError: If element doesn't reach state within timeout
        InvalidSelectorError: If selector is malformed
        
    Example:
        success = await page.wait_for_element("#button", state="visible")
    """
    pass
```

**11. NO REDUNDANT COMMENTS**
Never add comments that merely restate what the code already says. Comments should provide context, explain WHY (not WHAT), document non-obvious behavior, or warn about edge cases.

**Redundant comments (NEVER write these):**
```python
# Bad - restates obvious code
query_suffix = "deals"  # Set query_suffix to deals
type_filter_suffix=query_suffix,  # Use query_suffix as type filter suffix
count = len(records)  # Get the count of records
await page.goto(url)  # Navigate to URL
```

**Useful comments (DO write these):**
```python
# Good - explains WHY or provides context
query_suffix = "deals"  # S3 path component for organizing deal vs company data

# Good - warns about non-obvious behavior
type_filter_suffix=query_suffix,  # SNS consumers filter by this to process deals separately

# Good - explains business logic
if count == 0:
    # Empty results are valid for new queries - don't raise exception
    logger.warning("no_records_found")

# Good - documents workaround or edge case
await asyncio.sleep(0.1)  # Cloudflare detection if we proceed immediately
```

**When to add comments:**
- Explaining complex business logic or algorithms
- Documenting workarounds for bugs or platform limitations
- Warning about edge cases or non-obvious behavior
- Providing context that isn't clear from variable/function names
- Explaining WHY a particular approach was chosen over alternatives

**When NOT to add comments:**
- Describing what a line of code literally does (the code already says that)
- Repeating parameter names or function names
- Stating the obvious (e.g., "increment counter" above `i += 1`)
- Translating code to English without adding information

**12. NO MAGIC NUMBERS OR STRINGS**
Use named constants:
```python
# Good - named constants
DEFAULT_TIMEOUT_MS: int = 30000
RETRY_DELAY_MS: int = 1000
MAX_RETRY_ATTEMPTS: int = 3
API_ENDPOINT_PREFIX: str = "https://api.pitchbook.com/v1"

# Bad - magic numbers
await asyncio.sleep(1.0)
for i in range(3):
    ...
if response.status == 200:
    ...
```

**13. EXPLICIT IMPORTS**
Always use explicit imports, never `import *`:
```python
# Good
from typing import Optional, List, Dict, Any, Protocol
from datetime import datetime, timezone
from aws.facade import AWSClientFacade

# Bad
from typing import *
from aws.facade import *
```

**33. IMPORT ORDERING (PEP 8)**
All imports MUST be at the top of the file, grouped and ordered:
1. Standard library imports
2. Related third-party imports
3. Local application/library specific imports
4. Relative imports (from .module)

Within each group, imports should be alphabetically sorted.

```python
# Good - all imports at top, properly grouped
from typing import Optional, List
import asyncio
import os

import structlog
from playwright.async_api import Page

from authentication.manager import AuthManager
from aws.facade import AWSClientFacade
from managers.browser_manager import BrowserManager

from .navigation_manager import NavigationManager
from .models import SearchConfig

# Bad - mid-file imports
def some_function():
    from module import SomeClass  # NEVER do this
    ...
```

**Why this matters:**
- Type checkers can't analyze dependencies without top-level imports
- Harder to identify circular dependencies
- Makes module dependencies unclear
- Can cause subtle initialization order bugs

**Only exception:** Dynamic imports for optional features or plugin systems
(e.g., main.py USE_CASE selection), but these must be documented with comments.

**14. NO DEAD CODE**
- Do NOT comment out large blocks of code
- Use feature flags or conditional imports if needed
- Remove deprecated code only after full validation
- Use git for history, not commented code

---

## Error Handling Standards

**15. ERROR HANDLING MUST BE EXPLICIT**
- Every external API call must have explicit error handling
- Failed operations should log detailed context (URL, parameters, etc.)
- Never fail silently - always log or raise
- Use specific exception types (TimeoutError, ValueError, KeyError, etc.)
- Include retry logic for transient failures

```python
# Good - explicit error handling
try:
    response = await api_client.fetch_data(url)
    if response.status != 200:
        logger.error(
            "api_request_failed",
            url=url,
            status=response.status,
            reason=response.reason
        )
        raise ValueError(f"API returned {response.status}")
    return response.data
except asyncio.TimeoutError:
    logger.error("api_timeout", url=url, timeout_ms=timeout)
    raise
except Exception as e:
    logger.error("unexpected_api_error", url=url, error=str(e))
    raise

# Bad - swallowing errors
try:
    response = await api_client.fetch_data(url)
    return response.data
except:
    return None
```

**16. VALIDATION AT BOUNDARIES**
Validate data at system boundaries:
```python
def process_records(self, records: List[Dict[str, Any]]) -> List[ProcessedRecord]:
    """Process raw records."""
    if not records:
        raise ValueError("Records list cannot be empty")
    
    if not isinstance(records, list):
        raise TypeError(f"Expected list, got {type(records)}")
    
    # Process records...
```

---

## Logging Standards

**17. STRUCTURED LOGGING**
Use structured logging with context:
```python
logger.info(
    "processing_records",
    record_count=len(records),
    query_name=query_name,
    tab_type=tab_type
)

logger.error(
    "record_processing_failed",
    record_id=record.get("id"),
    error=str(e),
    query_name=query_name
)
```

**18. LOG LEVELS**
Use appropriate log levels:
- **DEBUG**: Detailed diagnostic information (loop iterations, variable values)
- **INFO**: General informational messages (start/complete operations, milestones)
- **WARNING**: Unexpected but recoverable conditions (retry attempts, partial failures)
- **ERROR**: Error conditions that may require intervention (API failures, data corruption)

**19. SENSITIVE DATA**
Never log sensitive data:
```python
# Bad
logger.info("login_attempt", username=username, password=password)

# Good
logger.info("login_attempt", username=username)
```

---

## Testing Standards

**20. MANUAL VALIDATION REQUIRED**
After implementing changes, document validation steps:
- [ ] Changes work as expected with actual data/systems
- [ ] No errors or warnings in logs
- [ ] Performance is acceptable
- [ ] Edge cases handled properly
- [ ] Downstream systems work correctly

**21. INTEGRATION OVER UNIT**
- Prioritize integration tests over unit tests
- Test with real dependencies when possible
- Mock only external services or slow operations
- Validate complete workflows, not just individual functions

**22. TEST WITH REAL DATA**
- Always test with actual production-like data
- Never rely solely on synthetic test data
- Validate against real system behavior
- Compare outputs with known good baselines

---

## Performance Considerations

**23. EFFICIENT DATA PROCESSING**
- Process data in batches when dealing with large datasets
- Use generators for large sequences to avoid loading everything in memory
- Profile code when performance is critical
- Document performance characteristics in comments

```python
# Good - generator for large datasets
def process_records_batch(records: List[Dict], batch_size: int = 100) -> Iterator[List[Dict]]:
    """Process records in batches to manage memory."""
    for i in range(0, len(records), batch_size):
        yield records[i:i + batch_size]

# Bad - loading everything
def process_all_records(records: List[Dict]) -> List[Dict]:
    return [process(r) for r in records]  # Could exhaust memory
```

**24. ASYNC OPERATIONS**
- Use async/await for I/O-bound operations
- Avoid blocking the event loop
- Use appropriate timeouts for all async operations
- Document async requirements in docstrings

---

## Configuration Management

**25. EXTERNALIZE CONFIGURATION**
- Never hardcode environment-specific values
- Use environment variables or config files
- Validate configuration at startup (fail fast)
- Document all configuration options

```python
# Good
bucket_name = os.getenv("S3_BUCKET_NAME")
if not bucket_name:
    raise ValueError("S3_BUCKET_NAME environment variable required")

# Bad
bucket_name = "prod-pitchbook-data"
```

**26. CONFIGURATION VALIDATION**
```python
@dataclass
class ServiceConfig:
    """Service configuration with validation."""
    
    api_url: str
    timeout_ms: int
    max_retries: int
    
    def __post_init__(self) -> None:
        if self.timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if not self.api_url.startswith("https://"):
            raise ValueError("api_url must use HTTPS")
```

**27. TEST SCRIPTS ENVIRONMENT LOADING**
All manual test scripts in `development/` that read environment variables MUST call `load_dotenv()` before accessing `os.getenv()`:

```python
# Good - test script with load_dotenv()
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file before reading environment variables
load_dotenv()

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Now safe to read environment variables
use_case = os.getenv("USE_CASE", "deals_last_3_days")
bucket = os.getenv("JSON_BUCKET")

# Bad - missing load_dotenv()
import os
import sys

# Directly reading env vars without load_dotenv()
use_case = os.getenv("USE_CASE")  # Won't load from .env file!
```

**Why this matters:**
- Test scripts are often run locally during development
- `.env` files provide convenient configuration without setting system env vars
- Without `load_dotenv()`, test scripts will fail when `.env` exists but env vars not set
- Matches pattern used in `main.py` and other entry points

**Pattern to follow:**
1. Import `load_dotenv` from `dotenv` package
2. Call `load_dotenv()` immediately after imports, before path manipulation
3. Then read environment variables with `os.getenv()`

---

## Naming Conventions

**27. DESCRIPTIVE NAMES**
Use clear, descriptive names:
```python
# Good
user_authentication_manager = UserAuthenticationManager()
total_processed_records = len(records)
is_valid_response = validate_response(response)

# Bad
mgr = UserAuthenticationManager()
total = len(records)
valid = validate_response(response)
```

**28. CONSISTENT NAMING**
- Classes: `PascalCase` (e.g., `DataProcessor`, `AuthManager`)
- Functions/methods: `snake_case` (e.g., `process_records`, `get_config`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- Private attributes: `_leading_underscore` (e.g., `_internal_cache`)
- Type variables: `T`, `K`, `V` or descriptive `RecordT`, `ConfigT`

---

## Documentation Standards

**29. README FILES**
Every module/package should have a README explaining:
- Purpose and responsibilities
- How to use the module
- Dependencies and requirements
- Examples of common use cases
- Known limitations or edge cases

**30. INLINE DOCUMENTATION**
- Document WHY decisions were made, not WHAT the code does
- Explain non-obvious algorithms or business logic
- Document assumptions and preconditions
- Warn about edge cases or limitations

---

## Security Best Practices

**31. CREDENTIAL HANDLING**
- Never commit credentials to version control
- Use environment variables or secret managers
- Rotate credentials regularly
- Log access to sensitive operations (without logging the credentials)

**32. INPUT VALIDATION**
- Validate all external input
- Sanitize data before use in queries or commands
- Use parameterized queries, never string concatenation
- Validate file paths to prevent directory traversal

---

## Critical Warnings

**33. NEVER BYPASS THESE RULES**
- ❌ Never deploy untested code to production
- ❌ Never skip validation "because it should work"
- ❌ Never ignore type errors or warnings
- ❌ Never commit commented-out code without explanation
- ❌ Never use `Any` type without documenting why
- ❌ Never catch exceptions without logging them

**34. WHEN IN DOUBT**
- Ask for code review before proceeding
- Test in isolated environment first
- Keep detailed logs of all attempts
- Document any unexpected behavior
- Consult relevant documentation
- Search for similar patterns in the codebase

---

## Success Indicators

A code change is complete when ALL of these are true:
- ✅ Code follows all standards in this document
- ✅ All type hints are complete and accurate
- ✅ All functions have docstrings
- ✅ No redundant or obvious comments
- ✅ All errors are handled explicitly
- ✅ Logs provide useful context
- ✅ Manual validation completed successfully
- ✅ No type errors or warnings
- ✅ Code reviewed and approved
