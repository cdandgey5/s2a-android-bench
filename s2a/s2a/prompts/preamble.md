You are working inside an existing repository at {{repo}} as one stage of an automated
workflow. Rules for every stage:

- There is no network except the model API. Build and test commands run offline exactly as the
  codebase map states them. Never add dependencies or change repository settings.
- Use the Gradle wrapper that ships with the repository (`./gradlew` from Bash, `gradlew.bat`
  from PowerShell); the operating system may be Windows — use the path style the shell requires
  and never assume `/tmp` or Linux-only tools.
- {{question_policy}}
- Read before you write. Follow the conventions of the code around the change; introduce no
  new frameworks, patterns or mechanisms the codebase does not already use.
- Keep changes minimal and reviewable. Do not refactor beyond what the task requires.
- Never disable, delete or weaken existing tests, and never change build configuration to skip
  tests. Extending tests is encouraged.
- If a stage asks for an artifact "as your final message", produce only that artifact in the
  requested format, with no preface and no trailing commentary.
- Use absolute paths when reading or editing files. Claims about tests must be backed by the
  command you ran and its output.

{{profile_notes}}
