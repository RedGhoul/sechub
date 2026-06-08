# go-snake

A small terminal Snake game written in Go, used to verify that this dev
container can compile Go code **with an external dependency**.

It depends on [`tcell`](https://github.com/gdamore/tcell) for terminal
rendering and input — a pure-Go library, so no CGO or system graphics
libraries are needed.

## Build & run

```bash
go build -o go-snake .
./go-snake          # needs a real terminal (TTY)
```

Controls:

- Arrow keys or **WASD** — steer
- **P** — pause
- **R** — restart after game over
- **Q** / **Esc** — quit

## Notes

- Builds to a single statically-linked binary (~3.7 MB).
- In a headless environment (no TTY) it exits immediately with
  `failed to init screen: open /dev/tty ...` — that is expected; the build
  itself still succeeds.

## Toolchain verified

- Go `1.24.7` (`linux/amd64`)
- `go get` / module download from the public proxy works in this container.
