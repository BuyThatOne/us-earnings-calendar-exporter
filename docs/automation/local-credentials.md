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
is created with owner-only mode `0700` when it does not already exist. On
non-POSIX systems, the command creates the empty regular file but does not
promise or attempt Unix mode enforcement.

Open the file in a local text editor and enter the dotenv-style
`ALPHAVANTAGE_API_KEY` entry and its local value. Do not put the value in a
shell command, shell history, this repository, logs, prompts, or generated
artifacts.

The loader uses a non-empty `ALPHAVANTAGE_API_KEY` process-environment value in
preference to the file. If the environment does not provide a key, the weekly
local Codex task uses the same loader and reads this file. The loader rejects a
file readable by group or others.
