import tkinter as tk
import random

root = tk.Tk()
root.title("Flappy Bird")
canvas = tk.Canvas(root, width=400, height=400, bg="cyan")
canvas.pack()

player = canvas.create_rectangle(125, 125, 150, 150, fill="red")
canvas.create_rectangle(0, 0, 400, 8, fill="green")
canvas.create_rectangle(0, 395, 400, 400, fill="green")
vel = 0
score = 0
pipes = []
gap = 0
spd = 0
score_text = canvas.create_text(200, 30, text=f"Score: {score}", font=("Arial", 20), fill="black")
def spawn_pipe():
    global gap
    gap_y = random.randint(100, 300)
    gap_size = 150 - gap

    top = canvas.create_rectangle(400, 0, 420, gap_y - gap_size//2, fill="green")
    bottom = canvas.create_rectangle(400, gap_y + gap_size//2, 420, 400, fill="green")


    pipes.append((top, bottom))

def overlap(a, b):
    ax1, ay1, ax2, ay2 = canvas.coords(a)
    bx1, by1, bx2, by2 = canvas.coords(b)
    return not (ax2 < bx1 or ax1 > bx2 or ay2 < by1 or ay1 > by2)

def update():
    global vel
    global score
    global spd
    global gap
    vel += 0.05
    canvas.move(player, 0, vel)

    # Player boundaries
    x1, y1, x2, y2 = canvas.coords(player)
    if y2 > 400 or y1 < 0:
        print("Game Over")
        return

    # Move pipes
    for top, bottom in pipes:
        canvas.move(top, -2 - spd, 0)
        canvas.move(bottom, -2 - spd, 0)

    # Remove old pipes and spawn new ones
    first_top, first_bottom = pipes[0]
    px1, py1, px2, py2 = canvas.coords(first_top)
    if px2 < 0:
        canvas.delete(first_top)
        canvas.delete(first_bottom)
        pipes.pop(0)
        score = score + 1
        score = score
        canvas.itemconfig(score_text, text=f"Score: {score}")
        gap = gap + 0.1
        spd = spd + 0.01
        spawn_pipe()

    # Collision detection
    for top, bottom in pipes:
        if overlap(player, top) or overlap(player, bottom):
            print("Hit pipe")
            return

    root.after(16, update)

def jump(event):
    global vel
    vel = -2

root.bind("<space>", jump)
spawn_pipe()
update()
root.mainloop()
