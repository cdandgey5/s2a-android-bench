# Stage: spec

Write the specification for this change as your final message, in this format:

```
# Spec: <title>
## Goal
<one paragraph>
## Scope
- In: ...
- Out: ...
## Acceptance criteria
AC1. WHEN <condition/event> THE SYSTEM SHALL <observable behaviour>. — verified by: <test class.method | concrete observation>
AC2. ...
## Unchanged behaviour
UB1. THE SYSTEM SHALL CONTINUE TO <existing behaviour that neighbours this change>. — verified by: <existing test | observation>
UB2. ...
## Compatibility constraints
- Public APIs / persisted data / schemas / resources that must keep working: ...
- Migration needed: yes/no — how
## {{assumptions_or_questions_heading}}
- ...
## Risks
- <risk> — <mitigation>
```

Rules: every criterion is observable and verifiable by a unit test or a concrete check; use the
reproduction tests where they exist. Criteria describe behaviour, not implementation. Keep the
scope to the ticket; list tempting adjacent improvements under "Out". "Unchanged behaviour"
lists what must keep working around the change (every observable behaviour is depended on by
someone); for bugs it is mandatory. Specify the change, not the whole system. {{question_policy}}

## Ticket
{{ticket}}

## Locate analysis
{{locate}}

## Reproduction result
{{repro}}

## Codebase map (conventions)
{{map_conventions}}
