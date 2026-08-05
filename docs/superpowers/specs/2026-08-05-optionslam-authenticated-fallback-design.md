# OptionSlam Authenticated Fallback Design

## Goal

Extend the existing OptionSlam EVR enrichment so the Python workflow keeps its
public-first behavior but can use a locally stored authenticated fallback during
prototype development when the public fetch path is blocked by membership
gating.

## Scope

This design is limited to EVR retrieval. It does not broaden the options
research pipeline, change ranking logic, or alter the existing local-only
credentials model. The OptionSlam username and password remain machine-local
development credentials and must never be committed, printed, or written into
artifacts.

## Current Behavior

Today `OptionSlamEvrProvider` performs one unauthenticated `GET` against
`https://www.optionslam.com/{symbol}/`, parses EVR from the returned HTML, and
classifies membership-style pages as `authentication_required`. The pipeline
then records EVR as unavailable and continues.

On August 5, 2026, the local pipeline produced `optionslam_evr_request_failed`
for `NTES`, while a separate browser-assisted check was able to observe EVR on
the site. That mismatch means the prototype needs an investigation path as well
as a fallback path.

## Recommended Approach

Keep one provider and one public entrypoint:

- first attempt the current unauthenticated fetch;
- only if the response indicates membership gating, perform one authenticated
  login using locally loaded credentials;
- retry the symbol page on the same session and parse EVR from the authenticated
  response;
- cache the authenticated session for later symbols in the same process.

This is narrower than introducing a second provider or a new CLI mode. It
preserves the current public-first contract while making the prototype useful
for cases where the browser can see EVR but the raw HTTP path cannot.

## Credentials

Reuse the existing owner-only local credentials file:

```text
~/.config/earnings-options-research/credentials.env
```

Add two supported keys:

```text
OPTIONSLAM_USERNAME=<local username>
OPTIONSLAM_PASSWORD=<local password>
```

Environment values with the same names take precedence over the file, matching
the existing `ALPHAVANTAGE_API_KEY` behavior. The loader reads only named keys,
accepts comments and blank lines, and never logs or exposes the parsed values.

## Provider Behavior

`OptionSlamEvrProvider.fetch_public_evr(symbol)` becomes public-first with
authenticated fallback:

1. Build the existing public symbol URL and issue one `GET`.
2. Parse the page and status as today.
3. If EVR is available, return immediately without attempting login.
4. If the page indicates membership gating and both credentials exist, log in
   once on the session, then re-request the symbol URL and parse EVR again.
5. If login succeeds but EVR is still missing, return a nonfatal unavailable
   status instead of raising.
6. If credentials are absent, invalid, or login fails, return a nonfatal
   unavailable status and continue the pipeline.

The provider must not retry broadly, rotate endpoints, or introduce browser
automation for this prototype.

## Status Model

The result model should distinguish the paths that matter operationally:

- `available`: EVR parsed successfully.
- `authentication_required`: the unauthenticated page is gated and no
  authenticated fallback was attempted or it could not proceed.
- `login_failed`: authenticated fallback was attempted but login did not
  establish a usable session.
- `not_found`: the final inspected page did not contain EVR.
- `request_failed`: network or HTTP failure prevented a usable final response.

If the implementation can preserve backward compatibility while adding a more
specific authenticated-fallback failure status, prefer that.

## Investigation Requirement

Add a durable investigation task alongside the code change so the prototype can
explain why the current script failed for `NTES` on August 5, 2026 while a web
check succeeded.

The investigation should capture, without secrets:

- the exact HTTP status code and final classification from the current provider;
- whether the returned HTML was a membership page, a redirect target, or a page
  variant the parser does not currently recognize;
- whether the browser-observed EVR depended on an authenticated session,
  JavaScript-rendered content, or different headers/cookies;
- whether the root cause is parser brittleness, authentication gating, or
  request-shape differences.

The durable form can be one of:

- a targeted regression test fixture for the failing HTML shape;
- a small diagnostic script or test helper that records sanitized provider
  outcomes;
- or both, if both are needed to keep the repro reviewable.

The investigation output must not persist credential values, session cookies, or
full private HTML if that would expose account-only content.

## Error Handling

- Missing OptionSlam credentials: skip authenticated fallback.
- Partial credentials: treat as unavailable configuration and skip login.
- Login endpoint or CSRF contract changes: classify as `login_failed` and keep
  the overall analysis nonfatal.
- Authenticated response without EVR: return `not_found`.
- Network failure before any usable parse: return `request_failed`.

## Testing

Implementation follows test-first development.

Minimum coverage:

- credentials loader reads `OPTIONSLAM_USERNAME` and `OPTIONSLAM_PASSWORD` from
  the local file with environment precedence;
- public EVR success does not attempt login;
- membership-gated public response triggers one authenticated fallback when
  credentials are present;
- authenticated fallback can parse EVR from a membership-only fixture;
- failed login is classified without raising and without retry loops;
- an investigation fixture or helper reproduces the current `NTES` failure class
  so the root cause is reviewable after the change.

## Acceptance Criteria

- The weekly options analysis can still run with no OptionSlam credentials.
- With local OptionSlam credentials configured, the provider attempts
  authentication only after a gated public response.
- EVR retrieval for gated symbols remains supplemental and nonfatal.
- The repository contains a durable repro or diagnostic for the August 5, 2026
  `NTES` failure mode.
