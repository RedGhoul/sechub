// Command go-snake is a small terminal Snake game built with the tcell
// library. It exists to demonstrate that this dev container can compile Go
// code that depends on an external module.
//
// Controls: arrow keys or WASD to steer, P to pause, Q or Esc to quit.
package main

import (
	"fmt"
	"math/rand"
	"os"
	"time"

	"github.com/gdamore/tcell/v2"
)

type point struct{ x, y int }

type direction int

const (
	dirUp direction = iota
	dirDown
	dirLeft
	dirRight
)

// opposite reports whether two directions are direct reverses of each other,
// which the snake is not allowed to do in a single step.
func (d direction) opposite(o direction) bool {
	switch d {
	case dirUp:
		return o == dirDown
	case dirDown:
		return o == dirUp
	case dirLeft:
		return o == dirRight
	case dirRight:
		return o == dirLeft
	}
	return false
}

type game struct {
	screen tcell.Screen
	w, h   int // playable area (inside the border)

	snake []point // head is the last element
	dir   direction
	food  point
	score int

	paused bool
	over   bool
	rng    *rand.Rand
}

func newGame(s tcell.Screen) *game {
	w, h := s.Size()
	g := &game{
		screen: s,
		w:      w - 2,
		h:      h - 2,
		dir:    dirRight,
		rng:    rand.New(rand.NewSource(time.Now().UnixNano())),
	}
	g.reset()
	return g
}

func (g *game) reset() {
	cx, cy := g.w/2, g.h/2
	g.snake = []point{{cx - 2, cy}, {cx - 1, cy}, {cx, cy}}
	g.dir = dirRight
	g.score = 0
	g.over = false
	g.paused = false
	g.placeFood()
}

func (g *game) placeFood() {
	for {
		p := point{g.rng.Intn(g.w), g.rng.Intn(g.h)}
		if !g.onSnake(p) {
			g.food = p
			return
		}
	}
}

func (g *game) onSnake(p point) bool {
	for _, s := range g.snake {
		if s == p {
			return true
		}
	}
	return false
}

func (g *game) head() point { return g.snake[len(g.snake)-1] }

// step advances the simulation by one tick.
func (g *game) step() {
	if g.paused || g.over {
		return
	}

	h := g.head()
	switch g.dir {
	case dirUp:
		h.y--
	case dirDown:
		h.y++
	case dirLeft:
		h.x--
	case dirRight:
		h.x++
	}

	// Wall collision.
	if h.x < 0 || h.x >= g.w || h.y < 0 || h.y >= g.h {
		g.over = true
		return
	}
	// Self collision.
	if g.onSnake(h) {
		g.over = true
		return
	}

	g.snake = append(g.snake, h)
	if h == g.food {
		g.score++
		g.placeFood()
	} else {
		// Move forward: drop the tail.
		g.snake = g.snake[1:]
	}
}

func (g *game) setDir(d direction) {
	if !g.dir.opposite(d) {
		g.dir = d
	}
}

// draw renders the full frame.
func (g *game) draw() {
	g.screen.Clear()

	borderStyle := tcell.StyleDefault.Foreground(tcell.ColorGray)
	snakeStyle := tcell.StyleDefault.Foreground(tcell.ColorGreen)
	headStyle := tcell.StyleDefault.Foreground(tcell.ColorLime).Bold(true)
	foodStyle := tcell.StyleDefault.Foreground(tcell.ColorRed).Bold(true)
	textStyle := tcell.StyleDefault.Foreground(tcell.ColorWhite)

	// Border around the playfield.
	for x := 0; x <= g.w+1; x++ {
		g.screen.SetContent(x, 0, '─', nil, borderStyle)
		g.screen.SetContent(x, g.h+1, '─', nil, borderStyle)
	}
	for y := 0; y <= g.h+1; y++ {
		g.screen.SetContent(0, y, '│', nil, borderStyle)
		g.screen.SetContent(g.w+1, y, '│', nil, borderStyle)
	}
	g.screen.SetContent(0, 0, '┌', nil, borderStyle)
	g.screen.SetContent(g.w+1, 0, '┐', nil, borderStyle)
	g.screen.SetContent(0, g.h+1, '└', nil, borderStyle)
	g.screen.SetContent(g.w+1, g.h+1, '┘', nil, borderStyle)

	// Food.
	g.screen.SetContent(g.food.x+1, g.food.y+1, '●', nil, foodStyle)

	// Snake body, then head on top.
	for i, s := range g.snake {
		style, ch := snakeStyle, '█'
		if i == len(g.snake)-1 {
			style, ch = headStyle, '◆'
		}
		g.screen.SetContent(s.x+1, s.y+1, ch, nil, style)
	}

	g.drawText(0, g.h+2, textStyle,
		fmt.Sprintf(" Score: %d   [arrows/WASD] move  [P] pause  [Q] quit ", g.score))

	if g.paused {
		g.drawCentered(textStyle.Bold(true), "PAUSED")
	}
	if g.over {
		g.drawCentered(tcell.StyleDefault.Foreground(tcell.ColorRed).Bold(true),
			fmt.Sprintf("GAME OVER — score %d — press R to restart, Q to quit", g.score))
	}

	g.screen.Show()
}

func (g *game) drawText(x, y int, style tcell.Style, s string) {
	for i, r := range s {
		g.screen.SetContent(x+i, y, r, nil, style)
	}
}

func (g *game) drawCentered(style tcell.Style, s string) {
	x := (g.w + 2 - len(s)) / 2
	if x < 0 {
		x = 0
	}
	g.drawText(x, (g.h+2)/2, style, s)
}

func main() {
	screen, err := tcell.NewScreen()
	if err != nil {
		fmt.Fprintln(os.Stderr, "failed to create screen:", err)
		os.Exit(1)
	}
	if err := screen.Init(); err != nil {
		fmt.Fprintln(os.Stderr, "failed to init screen:", err)
		os.Exit(1)
	}
	defer screen.Fini()

	g := newGame(screen)

	// Input runs on its own goroutine and feeds events into a channel.
	events := make(chan tcell.Event)
	quit := make(chan struct{})
	go func() {
		for {
			events <- screen.PollEvent()
			select {
			case <-quit:
				return
			default:
			}
		}
	}()

	ticker := time.NewTicker(90 * time.Millisecond)
	defer ticker.Stop()

	g.draw()
	for {
		select {
		case <-ticker.C:
			g.step()
			g.draw()
		case ev := <-events:
			switch ev := ev.(type) {
			case *tcell.EventResize:
				screen.Sync()
				w, h := screen.Size()
				g.w, g.h = w-2, h-2
				g.draw()
			case *tcell.EventKey:
				if handleKey(g, ev) {
					close(quit)
					return
				}
			}
		}
	}
}

// handleKey applies a key press and reports whether the game should exit.
func handleKey(g *game, ev *tcell.EventKey) (exit bool) {
	switch ev.Key() {
	case tcell.KeyEscape, tcell.KeyCtrlC:
		return true
	case tcell.KeyUp:
		g.setDir(dirUp)
	case tcell.KeyDown:
		g.setDir(dirDown)
	case tcell.KeyLeft:
		g.setDir(dirLeft)
	case tcell.KeyRight:
		g.setDir(dirRight)
	case tcell.KeyRune:
		switch ev.Rune() {
		case 'q', 'Q':
			return true
		case 'w', 'W':
			g.setDir(dirUp)
		case 's', 'S':
			g.setDir(dirDown)
		case 'a', 'A':
			g.setDir(dirLeft)
		case 'd', 'D':
			g.setDir(dirRight)
		case 'p', 'P':
			g.paused = !g.paused
		case 'r', 'R':
			if g.over {
				g.reset()
			}
		}
	}
	return false
}
