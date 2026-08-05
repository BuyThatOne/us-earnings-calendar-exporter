# Local Credentials Setup

The options-research CLI reads the Alpha Vantage key from this machine-local
file when the process environment does not provide one:

```text
~/.config/earnings-options-research/credentials.env
```

The file and its parent directory are created by the one-time setup command:

```bash
PYTHONPATH=src python3 -m earnings_export init-local-credentials
```

The command prints only the file path. It does not accept a key argument. It
does not accept extra arguments. It does not write key material. On POSIX
systems, the file is created empty with owner-only mode `0600`; the directory
is created with owner-only mode `0700` when it does not already exist. POSIX
support requires the platform to provide `O_NOFOLLOW`; if it is unavailable,
the command and loader fail with a security error instead of opening the
credentials path.

On non-POSIX systems, secure atomic no-follow access to an existing credentials
path is unavailable. The loader therefore refuses to read any existing
credentials path and the initializer refuses to modify one. The initializer
can create a genuinely absent empty file with an exclusive create, but that
file cannot be loaded by this application on non-POSIX systems. Use a
non-empty `ALPHAVANTAGE_API_KEY` environment value on those platforms instead.

Open the file in a local text editor and enter the dotenv-style
`ALPHAVANTAGE_API_KEY`, `OPTIONSLAM_USERNAME`, and `OPTIONSLAM_PASSWORD`
entries and their local values. The OptionSlam credentials use this same
owner-only credentials file. Keep all credential values local; they must never
be committed. Do not put them in a shell command, shell history, this repository,
logs, prompts, or generated artifacts.

The loader uses non-empty process-environment values in preference to the file
(environment precedence) for `ALPHAVANTAGE_API_KEY`, `OPTIONSLAM_USERNAME`, and
`OPTIONSLAM_PASSWORD`. If the environment does not provide a value, the weekly
local Codex task uses the same loader and reads this file. The loader rejects a
file readable by group or others on POSIX systems.
