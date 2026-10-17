# Stage: intake

Turn the request below into a normalized ticket. Do not look at the code yet beyond confirming
the repository exists. Return the ticket as your final message in exactly this format:

```
# <title, one line>
type: bug | feature | refactor | chore
size: S | M | L          # S = one file, obvious; M = a few files in one module; L = several modules or persisted data
## Description
<the request, restated precisely; keep every concrete detail the requester gave>
## Done when
- <observable outcome 1>
- <observable outcome 2>
## Constraints
- <anything the request implies must not change, or must be kept compatible>
## Unknowns
- <things the request does not say that will matter; later stages resolve them by assumption>
```

## Request

{{prompt}}
