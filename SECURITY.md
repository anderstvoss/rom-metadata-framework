# Security Policy

## Supported versions

ROM Metadata Framework is currently pre-1.0. Security fixes are applied to the
current `main` development line unless a release-specific support policy is
announced later.

## Reporting a vulnerability

Do not include credentials, tokens, private ROM-library paths, private
infrastructure details, or other secrets in a public issue.

For a vulnerability that can be discussed publicly without exposing sensitive
information, open a GitHub issue with a minimal reproducible description.

For a vulnerability that requires private coordination, use GitHub private
vulnerability reporting from the repository Security interface when that
facility is available. If private reporting is unavailable, contact the project
maintainer privately through GitHub before disclosing sensitive details.

## Scope

Security-relevant reports can include:

- unsafe command or subprocess handling;
- path traversal or unintended file replacement;
- archive or temporary-file handling;
- credential or token disclosure;
- unsafe handling of untrusted backend/provider output;
- packaging or dependency integrity issues;
- repository sanitation failures that could publish private environment data.

The framework intentionally invokes external tools without a command shell and
treats file replacement as an explicit operation. Changes affecting those
boundaries should receive additional review.
