from tkinter import *
import os, random, time, math
import pygame

TARGET = 100
SPAWN_MARGIN = TARGET // 2

PLAYER_SPEED = 10
BULLET_SPEED = 7
ENEMY_DOWN_SPEED = 1.6

SHOOT_DELAY = 400
ENEMY_BASE_COOLDOWN = 1600
INVINCIBLE_TIME = 1500

MAX_HP = 3
SCORE_FILE = "score.txt"

PLAYER_HIT = 0.15
ENEMY_HIT = 0.35

GUARD_MAX = 100
GUARD_HIT_COST = 35
GUARD_REGEN_PER_SEC = 22
GUARD_BREAK_COOLDOWN = 900

SHOTGUN_COST = 40
SHOTGUN_ANGLES = [-20, -10, 0, 10, 20]

IMG_DIR = "images"
SOUND_DIR = "sounds"

def img(name): return os.path.join(IMG_DIR, name)
def snd(name): return os.path.join(SOUND_DIR, name)

def load_high_score():
    if not os.path.exists(SCORE_FILE):
        return 0
    try:
        with open(SCORE_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip() or "0")
    except:
        return 0

def save_high_score(score):
    with open(SCORE_FILE, "w", encoding="utf-8") as f:
        f.write(str(score))

def load_png(path):
    base = PhotoImage(file=path)
    scale = max(1, base.width() // TARGET)
    return base.subsample(scale, scale)

def load_gif(path, zoom=1):
    frames = []
    scale = max(1, PhotoImage(file=path, format="gif -index 0").width() // TARGET)
    i = 0
    while True:
        try:
            f = PhotoImage(file=path, format=f"gif -index {i}")
            if scale > 1:
                f = f.subsample(scale, scale)
            if zoom > 1:
                f = f.zoom(zoom, zoom)
            frames.append(f)
            i += 1
        except:
            break
    return frames

class DeathEffect:
    def __init__(self, canvas, x, y, frames, delay=80):
        self.canvas = canvas
        self.frames = frames
        self.idx = 0
        self.delay = delay
        self.item = canvas.create_image(x, y, image=frames[0])
        self.animate()

    def animate(self):
        if self.canvas.type(self.item) == "":
            return
        if self.idx >= len(self.frames):
            self.canvas.delete(self.item)
            return
        self.canvas.itemconfig(self.item, image=self.frames[self.idx])
        self.idx += 1
        self.canvas.after(self.delay, self.animate)

class Bullet:
    def __init__(self, canvas, x, y, img, vx, vy):
        self.canvas = canvas
        self.vx = vx
        self.vy = vy
        self.item = canvas.create_image(x, y, image=img)
    def move(self):
        self.canvas.move(self.item, self.vx, self.vy)
    def pos(self):
        return self.canvas.coords(self.item)
    def delete(self):
        self.canvas.delete(self.item)

class Enemy:
    def __init__(self, canvas, x, y, frames, hp, speed, kind):
        self.canvas = canvas
        self.frames = frames
        self.hp = hp
        self.max_hp = hp
        self.base_speed = speed
        self.speed = speed
        self.dir = random.choice([-1, 1])
        self.kind = kind
        self.phase = 1
        self.item = canvas.create_image(x, y, image=frames[0])
        self.idx = 0
        self.animate()

    def animate(self):
        if self.canvas.type(self.item) == "":
            return
        self.canvas.itemconfig(self.item, image=self.frames[self.idx])
        self.idx = (self.idx + 1) % len(self.frames)
        self.canvas.after(160 if self.kind == 99 else 120, self.animate)

    def move(self, cw, ch):
        if self.kind == 99 and self.phase == 1 and self.hp <= self.max_hp // 2:
            self.phase = 2
            self.speed = self.base_speed + 2

        x, y = self.canvas.coords(self.item)

        if self.speed > 0:
            x += self.speed * self.dir
            if x < -SPAWN_MARGIN:
                x = cw + SPAWN_MARGIN
            elif x > cw + SPAWN_MARGIN:
                x = -SPAWN_MARGIN

        y += ENEMY_DOWN_SPEED
        if y > ch + SPAWN_MARGIN:
            y = -SPAWN_MARGIN

        self.canvas.coords(self.item, x, y)

class Player:
    def __init__(self, canvas, frames, guard_img, bullet_img):
        self.canvas = canvas
        self.frames = frames
        self.guard_img = guard_img
        self.bullet_img = bullet_img

        self.item = canvas.create_image(400, 680, image=frames[0])
        self.hp = MAX_HP
        self.alive = True
        self.invincible = False
        self.last_shot = 0

        self.guarding = False
        self.guard = GUARD_MAX
        self.guard_cd_until = 0
        self.last_guard_tick = int(time.time() * 1000)

        self.idx = 0
        self.animate()

    def now(self):
        return int(time.time() * 1000)

    def animate(self):
        if not self.alive or self.canvas.type(self.item) == "":
            return
        if self.guarding:
            self.canvas.itemconfig(self.item, image=self.guard_img)
            self.canvas.after(100, self.animate)
            return
        self.canvas.itemconfig(self.item, image=self.frames[self.idx])
        self.idx = (self.idx + 1) % len(self.frames)
        self.canvas.after(100, self.animate)

    def move(self, dx, dy, cw, ch):
        if not self.alive:
            return
        self.canvas.move(self.item, dx, dy)
        x, y = self.canvas.coords(self.item)
        x = max(SPAWN_MARGIN, min(cw - SPAWN_MARGIN, x))
        y = max(SPAWN_MARGIN, min(ch - SPAWN_MARGIN, y))
        self.canvas.coords(self.item, x, y)

    def shoot(self):
        if self.guarding:
            return None
        now = self.now()
        if not self.alive or now - self.last_shot < SHOOT_DELAY:
            return None
        self.last_shot = now
        x, y = self.canvas.coords(self.item)
        return Bullet(self.canvas, x, y - 60, self.bullet_img, 0, -BULLET_SPEED)

    def shoot_shotgun(self):
        now = self.now()
        if not self.alive or self.guarding:
            return []
        if now < self.guard_cd_until:
            return []
        if self.guard < SHOTGUN_COST:
            return []
        self.guard -= SHOTGUN_COST

        x, y = self.canvas.coords(self.item)
        bullets = []
        for a in SHOTGUN_ANGLES:
            r = math.radians(a)
            vx = math.sin(r) * BULLET_SPEED
            vy = -math.cos(r) * BULLET_SPEED
            bullets.append(Bullet(self.canvas, x, y - 60, self.bullet_img, vx, vy))
        return bullets

    def set_guard(self, on):
        if not self.alive:
            self.guarding = False
            return
        now = self.now()
        if on:
            if now < self.guard_cd_until or self.guard <= 0:
                self.guarding = False
                return
            self.guarding = True
            self.canvas.itemconfig(self.item, image=self.guard_img)
        else:
            self.guarding = False

    def regen_guard(self):
        now = self.now()
        dt = max(0, now - self.last_guard_tick)
        self.last_guard_tick = now
        if self.guard >= GUARD_MAX:
            self.guard = GUARD_MAX
            return
        if self.guarding or now < self.guard_cd_until:
            return
        add = (GUARD_REGEN_PER_SEC * dt) / 1000.0
        self.guard = min(GUARD_MAX, self.guard + add)

    def take_guard_hit(self, cost):
        self.guard -= cost
        if self.guard <= 0:
            self.guard = 0
            self.guarding = False
            self.guard_cd_until = self.now() + GUARD_BREAK_COOLDOWN

class Game:
    def __init__(self):
        self.root = Tk()
        self.root.title("SpaceShooting")
        self.root.geometry("800x800")

        self.canvas = Canvas(self.root, bg="black")
        self.canvas.pack(fill=BOTH, expand=True)

        self.root.bind("<KeyPress>", self.on_key)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.root.bind("<Configure>", self.on_resize)
        self.root.bind("<Return>", self.on_enter)

        self.audio_ok = False
        self.sfx_hit = None
        self.sfx_explode = None
        self.sfx_shotgun = None
        self.init_audio()

        self.paused = False
        self.waiting_start = True
        self.build_menu()

        self.stars = []
        self.star_count = 110
        self.blink_on = True
        self.last_blink = int(time.time() * 1000)

        self.player_frames = load_gif(img("player.gif"))
        self.player_guard_img = load_png(img("player2.png"))

        self.enemy1_frames = load_gif(img("enemy1.gif"))
        self.enemy2_frames = load_gif(img("enemy2.gif"))
        self.boss_frames = load_gif(img("boss.gif"))
        self.death_frames = load_gif(img("death.gif"), zoom=2)

        self.bullet_player = load_png(img("attack(player).png"))
        self.bullet_enemy = load_png(img("attack(enemy).png"))

        self.stage = 1
        self.score = 0
        self.high = load_high_score()
        self.game_over = False
        self.stage_lock = True

        self.shoot_job = None

        self.player = Player(self.canvas, self.player_frames, self.player_guard_img, self.bullet_player)
        self.enemies = []
        self.player_bullets = []
        self.enemy_bullets = []

        self.boss_hp_bar = None
        self.boss_hp_text = None
        self.guard_bar = None
        self.guard_text = None

        self.ui = self.canvas.create_text(10, 10, anchor="nw", fill="white", font=("Consolas", 16))
        self.hearts = self.canvas.create_text(10, 40, anchor="nw", fill="red", font=("Consolas", 22))
        self.center = self.canvas.create_text(400, 400, fill="white", font=("Consolas", 32))

        self.keys = set()

        self.init_starfield()
        self.show_start_screen()

        self.loop()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def init_audio(self):
        try:
            pygame.mixer.init()
            bgm_path = snd("bgm.mp3")
            if os.path.exists(bgm_path):
                pygame.mixer.music.load(bgm_path)
                pygame.mixer.music.set_volume(0.5)
                pygame.mixer.music.play(-1)

            hit_path = snd("hit.wav")
            exp_path = snd("explode.wav")
            shot_path = snd("shotgun.wav")

            self.sfx_hit = pygame.mixer.Sound(hit_path) if os.path.exists(hit_path) else None
            self.sfx_explode = pygame.mixer.Sound(exp_path) if os.path.exists(exp_path) else None
            self.sfx_shotgun = pygame.mixer.Sound(shot_path) if os.path.exists(shot_path) else None

            if self.sfx_hit: self.sfx_hit.set_volume(0.8)
            if self.sfx_explode: self.sfx_explode.set_volume(0.9)
            if self.sfx_shotgun: self.sfx_shotgun.set_volume(0.75)

            self.audio_ok = True
        except:
            self.audio_ok = False
            self.sfx_hit = None
            self.sfx_explode = None
            self.sfx_shotgun = None

    def play_hit(self):
        if self.sfx_hit:
            try: self.sfx_hit.play()
            except: pass

    def play_explode(self):
        if self.sfx_explode:
            try: self.sfx_explode.play()
            except: pass

    def play_shotgun(self):
        if self.sfx_shotgun:
            try: self.sfx_shotgun.play()
            except: pass

    def music_pause(self):
        if self.audio_ok:
            try: pygame.mixer.music.pause()
            except: pass

    def music_unpause(self):
        if self.audio_ok:
            try: pygame.mixer.music.unpause()
            except: pass

    def on_close(self):
        try:
            if self.audio_ok:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
        except:
            pass
        self.root.destroy()

    def build_menu(self):
        menubar = Menu(self.root)

        game_menu = Menu(menubar, tearoff=0)
        game_menu.add_command(label="시작 (Enter)", command=self.start_game)
        game_menu.add_command(label="타이틀로", command=self.restart_to_title)
        game_menu.add_separator()
        game_menu.add_command(label="일시정지 (P)", command=self.toggle_pause)
        game_menu.add_command(label="재개", command=self.resume)
        game_menu.add_separator()
        game_menu.add_command(label="종료", command=self.on_close)
        menubar.add_cascade(label="Game", menu=game_menu)

        opt_menu = Menu(menubar, tearoff=0)
        opt_menu.add_command(label="전체화면 토글 (F11)", command=self.toggle_fullscreen)
        opt_menu.add_command(label="전체화면 해제 (ESC)", command=self.exit_fullscreen)
        opt_menu.add_command(label="창 크기 초기화 (800x800)", command=self.reset_window_size)
        menubar.add_cascade(label="Options", menu=opt_menu)

        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="조작 방법 보기", command=self.show_controls)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self.exit_fullscreen())
        self.root.bind("p", lambda e: self.toggle_pause())
        self.root.bind("P", lambda e: self.toggle_pause())

    def show_controls(self):
        text = (
            "조작 방법\n"
            "--------------------------------\n"
            "이동: 방향키\n"
            "발사: Ctrl\n"
            "샷건: Z (가드 40 소모)\n"
            "가드: Shift\n"
            "\n"
            "기타\n"
            "--------------------------------\n"
            "시작: Enter\n"
            "타이틀: 메뉴에서 타이틀로\n"
            "일시정지: P\n"
            "전체화면: F11 (해제: ESC)\n"
        )
        self.canvas.itemconfig(self.center, text=text)
        self.root.after(3000, lambda: (not self.game_over) and (not self.paused) and (not self.waiting_start) and self.canvas.itemconfig(self.center, text=""))

    def toggle_fullscreen(self):
        cur = bool(self.root.attributes("-fullscreen"))
        self.root.attributes("-fullscreen", not cur)

    def exit_fullscreen(self):
        self.root.attributes("-fullscreen", False)

    def reset_window_size(self):
        self.root.attributes("-fullscreen", False)
        self.root.geometry("800x800")

    def toggle_pause(self):
        if self.game_over or self.waiting_start:
            return
        self.paused = not self.paused
        if self.paused:
            self.music_pause()
            self.canvas.itemconfig(self.center, text="PAUSED\n(Press P to Resume)")
        else:
            self.music_unpause()
            self.canvas.itemconfig(self.center, text="")

    def resume(self):
        if self.game_over or self.waiting_start:
            return
        self.paused = False
        self.music_unpause()
        self.canvas.itemconfig(self.center, text="")

    def cw(self): return max(1, self.canvas.winfo_width())
    def ch(self): return max(1, self.canvas.winfo_height())

    def clear_starfield(self):
        for s in self.stars:
            try:
                self.canvas.delete(s["id"])
            except:
                pass
        self.stars.clear()

    def init_starfield(self):
        self.clear_starfield()
        cw, ch = self.cw(), self.ch()
        for _ in range(self.star_count):
            x = random.randint(0, cw)
            y = random.randint(0, ch)
            r = random.choice([1, 1, 1, 2, 2, 3])
            spd = random.uniform(0.7, 3.6)
            item = self.canvas.create_oval(x - r, y - r, x + r, y + r, fill="white", outline="")
            self.canvas.tag_lower(item)
            self.stars.append({"id": item, "spd": spd, "r": r})

    def update_starfield(self):
        cw, ch = self.cw(), self.ch()
        for s in self.stars:
            if self.canvas.type(s["id"]) == "":
                continue
            x1, y1, x2, y2 = self.canvas.coords(s["id"])
            r = s["r"]
            x = (x1 + x2) / 2
            y = (y1 + y2) / 2
            y += s["spd"] * (0.6 if self.paused or self.game_over or self.waiting_start else 1.0)
            if y > ch + 6:
                y = -6
                x = random.randint(0, cw)
            self.canvas.coords(s["id"], x - r, y - r, x + r, y + r)
            self.canvas.tag_lower(s["id"])

    def show_start_screen(self):
        self.waiting_start = True
        self.paused = False
        self.game_over = False
        self.stage_lock = True
        self.canvas.itemconfig(
            self.center,
            text=(
                "SpaceShooting\n\n"
                "ENTER 키를 누르면 시작!\n\n"
                "이동: 방향키   발사: Ctrl\n"
                "샷건: Z        가드: Shift\n\n"
                f"HIGH SCORE : {self.high}"
            )
        )

    def on_enter(self, event=None):
        if self.waiting_start:
            self.start_game()

    def on_resize(self, e):
        self.init_starfield()
        if self.player.alive and self.canvas.type(self.player.item) != "":
            x, y = self.canvas.coords(self.player.item)
            x = max(SPAWN_MARGIN, min(e.width - SPAWN_MARGIN, x))
            y = max(SPAWN_MARGIN, min(e.height - SPAWN_MARGIN, y))
            self.canvas.coords(self.player.item, x, y)

    def clamp_x(self, x):
        return max(SPAWN_MARGIN, min(self.cw() - SPAWN_MARGIN, x))

    def hit(self, a, b, ra, rb):
        ax, ay = self.canvas.coords(a)
        bx, by = self.canvas.coords(b)
        ra *= TARGET
        rb *= TARGET
        return (ax - bx) ** 2 + (ay - by) ** 2 <= (ra + rb) ** 2

    def start_game(self):
        if not self.waiting_start and not self.game_over:
            return

        self.waiting_start = False
        self.paused = False
        self.game_over = False
        self.music_unpause()

        self.stage = 1
        self.score = 0
        self.stage_lock = True

        if self.shoot_job is not None:
            try:
                self.root.after_cancel(self.shoot_job)
            except:
                pass
            self.shoot_job = None

        self.canvas.delete("all")
        self.init_starfield()

        self.enemies.clear()
        self.player_bullets.clear()
        self.enemy_bullets.clear()

        self.boss_hp_bar = None
        self.boss_hp_text = None
        self.guard_bar = None
        self.guard_text = None

        self.player = Player(self.canvas, self.player_frames, self.player_guard_img, self.bullet_player)

        self.ui = self.canvas.create_text(10, 10, anchor="nw", fill="white", font=("Consolas", 16))
        self.hearts = self.canvas.create_text(10, 40, anchor="nw", fill="red", font=("Consolas", 22))
        self.center = self.canvas.create_text(self.cw() / 2, self.ch() / 2, fill="white", font=("Consolas", 32))
        self.keys = set()

        self.canvas.itemconfig(self.center, text="")
        self.start_stage()
        self.enemy_shoot_loop()
        self.stage_lock = False

    def start_stage(self):
        for en in self.enemies:
            if self.canvas.type(en.item) != "":
                self.canvas.delete(en.item)
        self.enemies.clear()

        if self.boss_hp_bar:
            self.canvas.delete(self.boss_hp_bar)
            self.boss_hp_bar = None
        if self.boss_hp_text:
            self.canvas.delete(self.boss_hp_text)
            self.boss_hp_text = None

        pattern = (self.stage - 1) % 3 + 1
        wave = (self.stage - 1) // 3
        count = 3 + wave
        speed = 2 + wave

        self.canvas.itemconfig(self.center, text=f"STAGE {self.stage}")
        self.canvas.after(800, lambda: (not self.paused) and (not self.waiting_start) and self.canvas.itemconfig(self.center, text=""))

        if pattern == 1:
            for i in range(count):
                x = self.clamp_x(self.cw() * (i + 1) / (count + 1))
                self.enemies.append(Enemy(self.canvas, x, 220, self.enemy1_frames, 1, 0, 1))

        elif pattern == 2:
            for i in range(count):
                x = self.clamp_x(self.cw() * (i + 1) / (count + 1))
                if i % 2:
                    self.enemies.append(Enemy(self.canvas, x, 220, self.enemy2_frames, 2, speed + 1, 2))
                else:
                    self.enemies.append(Enemy(self.canvas, x, 220, self.enemy1_frames, 1, speed, 1))

        else:
            boss_hp = 6 + wave * 2
            boss_x = self.clamp_x(self.cw() / 2)
            self.enemies.append(Enemy(self.canvas, boss_x, 160, self.boss_frames, boss_hp, 1 + wave, 99))

            side_n = 2 + wave
            for i in range(side_n):
                x = self.clamp_x(self.cw() * (i + 1) / (side_n + 1))
                self.enemies.append(Enemy(self.canvas, x, 280, self.enemy2_frames, 2, speed + 1, 2))

    def draw_guard_ui(self):
        if self.guard_bar:
            self.canvas.delete(self.guard_bar)
        if self.guard_text:
            self.canvas.delete(self.guard_text)

        ratio = max(0.0, min(1.0, self.player.guard / GUARD_MAX))
        w = 180 * ratio
        x1, y1 = 10, 74
        x2, y2 = x1 + w, y1 + 14

        fill = "cyan" if self.player.guard_cd_until <= self.player.now() else "gray"
        self.guard_bar = self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="")
        self.guard_text = self.canvas.create_text(
            10, 92, anchor="nw", fill="white", font=("Consolas", 12),
            text=f"GUARD: {int(self.player.guard)}"
        )

    def draw_boss_hp_bar(self):
        boss = None
        for en in self.enemies:
            if en.kind == 99:
                boss = en
                break
        if not boss or boss.hp <= 0:
            if self.boss_hp_bar:
                self.canvas.delete(self.boss_hp_bar); self.boss_hp_bar = None
            if self.boss_hp_text:
                self.canvas.delete(self.boss_hp_text); self.boss_hp_text = None
            return

        if self.boss_hp_bar: self.canvas.delete(self.boss_hp_bar)
        if self.boss_hp_text: self.canvas.delete(self.boss_hp_text)

        ratio = boss.hp / boss.max_hp
        bar_w = 320 * ratio
        x1 = (self.cw() - 320) / 2
        x2 = x1 + bar_w
        color = "red" if boss.phase == 1 else "orange"

        self.boss_hp_bar = self.canvas.create_rectangle(x1, 22, x2, 40, fill=color, outline="")
        self.boss_hp_text = self.canvas.create_text(
            self.cw() / 2, 12, fill="white", font=("Consolas", 14),
            text=f"BOSS HP : {boss.hp} / {boss.max_hp}"
        )

    def on_key(self, e):
        self.keys.add(e.keysym)

        if self.waiting_start:
            return

        if self.game_over:
            if e.keysym.lower() == "r":
                self.restart_to_title()
            return

        if e.keysym in ("Shift_L", "Shift_R"):
            if not self.paused:
                self.player.set_guard(True)
            return

        if e.keysym in ("Control_L", "Control_R"):
            if not self.paused:
                b = self.player.shoot()
                if b:
                    self.player_bullets.append(b)
            return

        if e.keysym.lower() == "z":
            if not self.paused:
                bullets = self.player.shoot_shotgun()
                if bullets:
                    self.play_shotgun()
                    for b in bullets:
                        self.player_bullets.append(b)

    def on_key_release(self, e):
        if e.keysym in self.keys:
            self.keys.remove(e.keysym)
        if e.keysym in ("Shift_L", "Shift_R"):
            self.player.set_guard(False)

    def enemy_shoot_loop(self):
        if (self.waiting_start or self.paused) and not self.game_over:
            self.shoot_job = self.root.after(120, self.enemy_shoot_loop)
            return
        if self.game_over:
            return

        if self.enemies:
            shooter = random.choice(self.enemies)
            sx, sy = self.canvas.coords(shooter.item)

            if shooter.kind == 99:
                angles = [-45, -30, -15, 0, 15, 30, 45] if shooter.phase == 2 else [-30, -15, 0, 15, 30]
                for a in angles:
                    r = math.radians(a)
                    self.enemy_bullets.append(Bullet(
                        self.canvas, sx, sy + 50, self.bullet_enemy,
                        math.sin(r) * BULLET_SPEED, math.cos(r) * BULLET_SPEED
                    ))
            elif shooter.kind == 2:
                for a in [-10, 0, 10]:
                    r = math.radians(a)
                    self.enemy_bullets.append(Bullet(
                        self.canvas, sx, sy + 50, self.bullet_enemy,
                        math.sin(r) * BULLET_SPEED, math.cos(r) * BULLET_SPEED
                    ))
            else:
                self.enemy_bullets.append(Bullet(self.canvas, sx, sy + 50, self.bullet_enemy, 0, BULLET_SPEED))

        cooldown = ENEMY_BASE_COOLDOWN + (self.stage // 3) * 150
        for en in self.enemies:
            if en.kind == 99 and en.phase == 2:
                cooldown = max(700, cooldown - 650)
                break
        self.shoot_job = self.root.after(cooldown, self.enemy_shoot_loop)

    def player_hit(self):
        if not self.player.alive:
            return

        if self.player.guarding and self.player.guard > 0 and self.player.now() >= self.player.guard_cd_until:
            self.play_hit()
            self.player.take_guard_hit(GUARD_HIT_COST)
            return

        if self.player.invincible:
            return

        self.play_hit()
        self.player.hp -= 1

        if self.player.hp <= 0:
            self.game_over = True
            self.player.alive = False
            if self.canvas.type(self.player.item) != "":
                x, y = self.canvas.coords(self.player.item)
                self.canvas.delete(self.player.item)
                DeathEffect(self.canvas, x, y, self.death_frames, delay=90)
                self.play_explode()

            if self.score > self.high:
                self.high = self.score
                save_high_score(self.high)

            self.canvas.itemconfig(
                self.center,
                text=f"GAME OVER\n\nR 키를 눌러 타이틀로\n\nSCORE : {self.score}\nHIGH : {self.high}"
            )

    def loop(self):
        self.update_starfield()

        if self.waiting_start:
            now = int(time.time() * 1000)
            if now - self.last_blink >= 450:
                self.last_blink = now
                self.blink_on = not self.blink_on
                press = "ENTER 키를 누르면 시작!" if self.blink_on else " "
                self.canvas.itemconfig(
                    self.center,
                    text=(
                        "SpaceShooting\n\n"
                        f"{press}\n\n"
                        "이동: 방향키   발사: Ctrl\n"
                        "샷건: Z        가드: Shift\n\n"
                        f"HIGH SCORE : {self.high}"
                    )
                )
            self.canvas.itemconfig(self.ui, text=f"STAGE:{self.stage} SCORE:{self.score} HIGH:{self.high}")
            self.canvas.itemconfig(self.hearts, text="❤ " * max(0, self.player.hp))
            self.canvas.after(30, self.loop)
            return

        if not self.game_over:
            if self.paused:
                self.draw_boss_hp_bar()
                self.draw_guard_ui()
                self.canvas.itemconfig(self.ui, text=f"STAGE:{self.stage} SCORE:{self.score} HIGH:{self.high}")
                self.canvas.itemconfig(self.hearts, text="❤ " * max(0, self.player.hp))
                self.canvas.after(30, self.loop)
                return

            cw, ch = self.cw(), self.ch()

            dx = 0
            dy = 0
            if "Left" in self.keys: dx -= PLAYER_SPEED
            if "Right" in self.keys: dx += PLAYER_SPEED
            if "Up" in self.keys: dy -= PLAYER_SPEED
            if "Down" in self.keys: dy += PLAYER_SPEED
            if dx != 0 or dy != 0:
                if dx != 0 and dy != 0:
                    s = PLAYER_SPEED / (2 ** 0.5)
                    dx = s if dx > 0 else -s
                    dy = s if dy > 0 else -s
                self.player.move(dx, dy, cw, ch)

            self.player.regen_guard()

            for en in self.enemies:
                en.move(cw, ch)

            for b in self.player_bullets[:]:
                b.move()
                x, y = b.pos()
                if y < -50 or x < -50 or x > cw + 50:
                    b.delete(); self.player_bullets.remove(b); continue
                for en in self.enemies[:]:
                    if self.hit(b.item, en.item, 0.25, ENEMY_HIT):
                        en.hp -= 1
                        b.delete(); self.player_bullets.remove(b)
                        if en.hp <= 0:
                            ex, ey = self.canvas.coords(en.item)
                            self.canvas.delete(en.item)
                            self.enemies.remove(en)
                            DeathEffect(self.canvas, ex, ey, self.death_frames, delay=80)
                            self.play_explode()
                            self.score += 1000 if en.kind == 99 else 200 if en.kind == 2 else 100
                        break

            for b in self.enemy_bullets[:]:
                b.move()
                x, y = b.pos()
                if y > ch + 50 or x < -50 or x > cw + 50:
                    b.delete(); self.enemy_bullets.remove(b); continue
                if self.player.alive and self.hit(b.item, self.player.item, ENEMY_HIT, PLAYER_HIT):
                    b.delete(); self.enemy_bullets.remove(b)
                    self.player_hit()

            if not self.enemies and not self.stage_lock:
                self.stage_lock = True
                self.score += 500
                self.stage += 1
                self.start_stage()
                self.root.after(220, lambda: setattr(self, "stage_lock", False))

        self.draw_boss_hp_bar()
        self.draw_guard_ui()
        self.canvas.itemconfig(self.ui, text=f"STAGE:{self.stage} SCORE:{self.score} HIGH:{self.high}")
        self.canvas.itemconfig(self.hearts, text="❤ " * max(0, self.player.hp))
        self.canvas.after(30, self.loop)

    def restart_to_title(self):
        if self.shoot_job is not None:
            try:
                self.root.after_cancel(self.shoot_job)
            except:
                pass
            self.shoot_job = None

        self.canvas.delete("all")
        self.init_starfield()

        self.enemies.clear()
        self.player_bullets.clear()
        self.enemy_bullets.clear()

        self.boss_hp_bar = None
        self.boss_hp_text = None
        self.guard_bar = None
        self.guard_text = None

        self.stage = 1
        self.score = 0
        self.game_over = False
        self.paused = False

        self.player = Player(self.canvas, self.player_frames, self.player_guard_img, self.bullet_player)

        self.ui = self.canvas.create_text(10, 10, anchor="nw", fill="white", font=("Consolas", 16))
        self.hearts = self.canvas.create_text(10, 40, anchor="nw", fill="red", font=("Consolas", 22))
        self.center = self.canvas.create_text(self.cw() / 2, self.ch() / 2, fill="white", font=("Consolas", 32))
        self.keys = set()

        self.show_start_screen()

Game()

