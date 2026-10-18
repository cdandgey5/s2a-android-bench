Work in these steps, in order, and do not skip any:

1. Map: before changing anything, get oriented in the repository — its modules, how they depend on
   each other, where the code relevant to the ticket lives, and the repository's own conventions
   (instruction files, build setup, how tests are written and run).
2. Locate: find the exact code paths the ticket concerns and everything that calls them, so you
   know what a change could affect.
3. Reproduce or characterize: for a bug, write or run a unit test that shows the wrong behaviour
   before you fix it; for a feature or refactoring, pin the current behaviour you must keep with
   tests first.
4. Specify: state in a few sentences what must be true when you are done, including what must
   not change.
5. Plan: split the work into small steps that each leave the build green.
6. Implement in small steps: after each step compile and run the affected module's unit tests,
   and keep the change minimal and in the style of the surrounding code.
7. Self-review: re-read your whole diff against the ticket and the statement from step 4, run the
   affected modules' unit tests once more, and fix what you find.
