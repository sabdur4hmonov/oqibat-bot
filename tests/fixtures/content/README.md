# Test content only

These nine small banks preserve the former examples for deterministic tests.
`content_directory` copies them into a fresh temporary directory for each test;
runtime fixtures load that copy. Tests may replace individual items without
changing production content or another test's bank.

The real banks are in `data/`. Their validation test reads them explicitly and
has no fixed item-count assumptions. Do not copy production content here.
