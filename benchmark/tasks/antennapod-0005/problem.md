# Refactor: expose the episode sort comparators so other code can reuse the exact ordering

**Describe the change**

Every episode ordering the app offers (title, date, duration, file name, podcast title, size,
completion date) is built inside `FeedItemPermutors.getPermutor(SortOrder)`, and only as a
`Permutor` that reorders a whole list. Code that needs the *comparison* itself — for example to
insert a single episode at the right position, or to merge two already sorted lists — has no
way to get it and ends up re-implementing the ordering, with the risk of subtle differences
(null titles, missing media, case handling).

Please expose the comparison for each sort order:

- add `FeedItemPermutors.getComparator(SortOrder)` returning the `Comparator<FeedItem>` that
  defines that order;
- for orders that are not defined by comparing two episodes (random and both smart shuffle
  orders) it returns `null`;
- `GLOBAL_DEFAULT` resolves to the user's global sort order, as `getPermutor` already does;
- `getPermutor` uses these comparators, so the two can never disagree.

This is a refactoring: the order produced by `getPermutor` for every sort order must stay
exactly the same as today, including how items with missing titles, dates, media or podcast are
placed.
