import tkinter as tk
from tkinter import ttk
import random, math, time, json, os
import ctypes

# Fix blurry text on high-DPI displays
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Windows 8.1+
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # Windows Vista+
    except:
        pass  # Not on Windows or already set
# ---------- Config ----------
WINDOW_W = 800
WINDOW_H = 600
ROOM_ROWS = 2
ROOM_COLS = 5
MAX_SKILLS = 9
SAVE_FILE = "player_save.json"
ROOM_W = WINDOW_W // ROOM_COLS
ROOM_H = WINDOW_H // ROOM_ROWS
# ---------- Class-based automatic stat growth ----------
CLASS_STAT_GROWTH = {
    'Warrior': {'strength': 1, 'vitality': 1, 'agility': 1, 'intelligence': 0, 'wisdom': 0, 'will': 0, 'constitution': 1},
    'Mage':    {'strength': 0, 'vitality': 0, 'agility': 0, 'intelligence': 2, 'wisdom': 1, 'will': 1, 'constitution': 0},
    'Rogue':   {'strength': 1, 'vitality': 0, 'agility': 1, 'intelligence': 1, 'wisdom': 0, 'will': 1, 'constitution': 0},
    'Cleric':  {'strength': 0, 'vitality': 0, 'agility': 0, 'intelligence': 1, 'wisdom': 1, 'will': 2, 'constitution': 1},
    'Druid':   {'strength': 0, 'vitality': 1, 'agility': 1, 'intelligence': 1, 'wisdom': 2, 'will': 0, 'constitution': 1},
    'Monk':    {'strength': 0, 'vitality': 2, 'agility': 1, 'intelligence': 0, 'wisdom': 0, 'will': 0, 'constitution': 1},
    'Ranger':  {'strength': 1, 'vitality': 0, 'agility': 1, 'intelligence': 1, 'wisdom': 0, 'will': 1, 'constitution': 0},
}

# ---------- Utilities ----------
def clamp(v,a,b): return max(a,min(b,v))
def distance(a,b): return math.hypot(a[0]-b[0],a[1]-b[1])
def resolve_overlap(a, b):
    """Push objects a and b apart if overlapping."""
    dx = b.x - a.x
    dy = b.y - a.y
    dist = math.hypot(dx, dy)
    min_dist = a.size + b.size

    if dist < min_dist and dist > 0:
        overlap = min_dist - dist
        nx, ny = dx / dist, dy / dist
        a.x -= nx * overlap / 2
        a.y -= ny * overlap / 2
        b.x += nx * overlap / 2
        b.y += ny * overlap / 2
# ---------- Player ----------
class Player:
    def __init__(self,name='Hero',class_name='Warrior'):
        self.name=name; self.class_name=class_name
        self.x=WINDOW_W//2; self.y=WINDOW_H//2; self.size=16
        self.strength=5; self.vitality=5; self.agility=5
        self.intelligence=5; self.wisdom=5; self.will=5; self.constitution=3
        self.level=1; self.xp=0; self.xp_to_next=100
        self.stat_points=5; self.skill_points=0
        self.skills=[]; self.unlocked_skills=[]
        self.populate_skills()
        self.update_stats()
        self.hp = self.max_hp
        self.mana = self.max_mana
        self.active_skill_effects = {}

    def update_stats(self):
        self.max_hp=50+self.vitality*10
        self.hp=min(getattr(self,'hp',self.max_hp),self.max_hp)
        self.max_mana=20+self.intelligence*10
        self.mana=min(getattr(self,'mana',self.max_mana),self.max_mana)
        self.speed=2+self.agility*0.3
        self.atk=5+self.strength
        self.mag=2+self.will
        self.vit=2+self.vitality
        self.wis=2+self.wisdom
        self.hp_regen=0.2+self.vitality*0.07
        self.mana_regen=0.1+self.wisdom*0.15

    def populate_skills(self):
        def howl(summon, game):
            if not game.room.enemies:
                return

            owner = summon.owner if summon.owner else game.player
            target = min(game.room.enemies, key=lambda e: distance((summon.x, summon.y), (e.x, e.y)))
            angle_center = math.atan2(target.y - summon.y, target.x - summon.x)

            # Base parameters for Wi-Fi style slashes
            speed = 5
            life = 2.0
            damage = owner.wis / 2

            # Fire three slash projectiles with small size and spacing
            for i in range(3):
                radius = 6   # keep them thin
                length = 12 + i * 15   # short reach, spaced out (12, 27, 42)
                spawn_x = summon.x + math.cos(angle_center) * length
                spawn_y = summon.y + math.sin(angle_center) * length

                game.spawn_projectile(
                    spawn_x, spawn_y,
                    angle_center,
                    speed,
                    life,
                    radius,
                    "gray",
                    damage,
                    owner="summon",
                    stype="slash"   # reuse your slash projectile type
                )



        def summon_wolf(player, game):
            if player.mana < 10:
                return
            player.mana -= 10

            wolf = Summoned(
                "Wolf",
                hp=30 + player.wis,
                atk=5 + player.wis,              # <-- fixed here
                spd=3 + player.wis / 20,
                x=player.x + 20,
                y=player.y + 20,
                duration=15 + player.wis,
                role="loyal",
                owner=player,
                mana_upkeep=2.5
            )

            wolf.skills.append({
                'skill': howl,
                'name': 'Howl',
                'cooldown': 0.8,
                'last_used': 0
            })

            # Add wolf to active summons
            game.summons.append(wolf)
        def fire_trap(player, game):
            if player.mana < 15 or not game.room.enemies:
                return
            player.mana -= 15
            trap = Particle(
                player.x, player.y,
                size=5,
                color="orange",
                life=100.0,
                rtype="trap",
                atype="firetrap",
                angle=0
            )
            game.particles.append(trap)
        def frost_trap(player, game):
            if player.mana < 15 or not game.room.enemies:
                return
            player.mana -= 15
            trap = Particle(
                player.x, player.y,
                size=5,
                color="cyan",
                life=100.0,
                rtype="trap",
                atype="frosttrap",
                angle=0
            )
            game.particles.append(trap)

        def minor_heal(player, game):
            heal_amount = player.mag
            player.hp = min(player.max_hp, player.hp + heal_amount)

            # Create diamond particles around the player
            for i in range(6):
                angle = (math.pi * 2 / 6) * i
                ring = 20
                px = player.x + math.cos(angle) * ring
                py = player.y + math.sin(angle) * ring

                diamond = Particle(
                    px, py,
                    size=8,
                    color="gold",
                    life=1.0,
                    rtype="diamond"
                )
                game.particles.append(diamond)


        def rapid_strike(player, game):
            duration_ms = 3000   # 3 seconds
            tick_ms = 15         # update every 0.015s
            mana_cost_per_tick = 0.1

            def rapid_tick():
                if player.mana <= 0 or time.time() >= player._rapid_end:
                    player._rapid_active = False
                    return

                player.mana -= mana_cost_per_tick
                game.spawn_particle(player.x, player.y, 30, 'yellow', life=0.5)

                # Damage nearby enemies
                for e in list(game.room.enemies):
                    if distance((player.x, player.y), (e.x, e.y)) < 50:
                        game.damage_enemy(e, player.atk)

                # Delete projectiles that hit the shield radius
                for proj in list(game.projectiles):
                    d = distance((player.x, player.y), (proj.x, proj.y))
                    if d <= 30 + proj.radius:
                        game.projectiles.remove(proj)

                # Always reschedule next tick
                game.after(tick_ms, rapid_tick)

            if not getattr(player, "_rapid_active", False):
                player._rapid_active = True
                player._rapid_end = time.time() + (duration_ms / 1000.0)
                rapid_tick()


        def ground_pound(player, game):
            if player.mana < 10: 
                return
            player.mana -= 10

            # Shockwave parameters
            shockwave_radius = 20       # starting radius
            max_radius = 120            # how far the wave expands
            expansion_speed = 8         # pixels per frame
            damage = player.atk * 1.5

            # Create a particle that represents the expanding ring
            shockwave = Particle(
                player.x, player.y,
                size=shockwave_radius,
                color='white',
                life=0.5,               # short-lived visual
                rtype='shockwave',
                outline=True
            )
            shockwave.expansion_speed = expansion_speed
            shockwave.max_radius = max_radius
            shockwave.damage = damage
            game.particles.append(shockwave)

            # Apply immediate damage + knockback to enemies in range
            for e in list(game.room.enemies):
                d = distance((player.x, player.y), (e.x, e.y))
                if d < max_radius:
                    # Damage
                    game.damage_enemy(e, damage)

                    # Knockback
                    ang = math.atan2(e.y - player.y, e.x - player.x)
                    push_strength = (max_radius - d) * 0.3  # stronger if closer
                    e.x += math.cos(ang) * push_strength
                    e.y += math.sin(ang) * push_strength

        def thorn_whip(player, game):
            if player.mana < 5 or not game.room.enemies:
                return
            player.mana -= 5

            # Aim lash toward nearest enemy
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            angle_center = math.atan2(target.y - player.y, target.x - player.x)

            # Parameters - LONGER duration and reach
            whip_life = 1.2        # Increased from 0.6 to 1.2 seconds
            whip_radius = 100      # Increased from 80 to 100

            # Branch tip that animates out and back
            branch = Particle(
                player.x, player.y,
                size=8, color='#8B4513',  # Slightly bigger tip
                life=whip_life,
                rtype='branch',
                angle=angle_center,
                radius=whip_radius
            )
            game.particles.append(branch)

            # More leaves spread along the whip for better visual
            for i in range(8):  # Increased from 5 to 8 leaves
                offset = i * 12  # Closer spacing
                angle_offset = random.uniform(-0.15, 0.15)  # Less variation
                leaf = Particle(
                    player.x, player.y,
                    size=4, color='#228B22',  # Slightly bigger leaves
                    life=whip_life,
                    rtype='leaf',
                    angle=angle_center + angle_offset,
                    radius=whip_radius - offset
                )
                game.particles.append(leaf)

    # Immediate damage to enemies within the lash reach and arc
    
        def chi_strike(player, game):
            if player.hp < 3 or not game.room.enemies:
                return
            player.hp -= 3

            # Find nearest enemy
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            angle_center = math.atan2(target.y - player.y, target.x - player.x)

            # Slash parameters
            arc_radius = 40     # how far the blade reaches
            arc_width = math.pi/3 # angular width of the slash
            px, py = player.x, player.y

            # Spawn blade particle WITH ANGLE
            size = arc_radius
            # Offset distance so the blade appears further out
            offset = arc_radius // 2   # half the radius forward
            spawn_x = px + math.cos(angle_center) * offset
            spawn_y = py + math.sin(angle_center) * offset

            # Spawn blade particle at the offset position
            blade_particle = Particle(spawn_x, spawn_y, arc_radius, 'cyan', life=0.3, rtype='blade1', angle=angle_center)
            game.particles.append(blade_particle)

            for e in list(game.room.enemies):
                dx, dy = e.x - px, e.y - py
                dist = math.hypot(dx, dy)
                if dist <= arc_radius:
                    angle_to_enemy = math.atan2(dy, dx)
                    diff = (angle_to_enemy - angle_center + math.pi*2) % (math.pi*2)
                    if diff < arc_width/2 or diff > math.pi*2 - arc_width/2:
                        game.damage_enemy(e, 0)
            # Damage enemies in arc
        def strike(player, game):
            if player.mana < 2 or not game.room.enemies:
                return
            player.mana -= 2

            # Find nearest enemy
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            angle_center = math.atan2(target.y - player.y, target.x - player.x)

            # Slash parameters
            arc_radius = 30     # how far the blade reaches
            arc_width = math.pi/3 # angular width of the slash
            px, py = player.x, player.y

            # Spawn blade particle WITH ANGLE
            size = arc_radius
            # Offset distance so the blade appears further out
            offset = arc_radius // 2   # half the radius forward
            spawn_x = px + math.cos(angle_center) * offset
            spawn_y = py + math.sin(angle_center) * offset

            # Spawn blade particle at the offset position
            blade_particle = Particle(spawn_x, spawn_y, arc_radius, 'red', life=0.3, rtype='blade1', angle=angle_center)
            game.particles.append(blade_particle)

            for e in list(game.room.enemies):
                dx, dy = e.x - px, e.y - py
                dist = math.hypot(dx, dy)
                if dist <= arc_radius:
                    angle_to_enemy = math.atan2(dy, dx)
                    diff = (angle_to_enemy - angle_center + math.pi*2) % (math.pi*2)
                    if diff < arc_width/2 or diff > math.pi*2 - arc_width/2:
                        game.damage_enemy(e, 0)


            # Damage enemies in arc
        def dark_slash(player, game):
            if player.mana < 2 or not game.room.enemies:
                return
            player.mana -= 2

            # Find nearest enemy
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            angle_center = math.atan2(target.y - player.y, target.x - player.x)

            # Slash parameters
            arc_radius = 40     # how far the blade reaches
            arc_width = math.pi/3 # angular width of the slash
            px, py = player.x, player.y
            offset = 40 // 2   # half the radius forward
            spawn_x = px + math.cos(angle_center) * offset
            spawn_y = py + math.sin(angle_center) * offset
            # Spawn blade particle WITH ANGLE
            size = arc_radius
            blade_particle = Particle(px, py, size, 'purple', life=0.3, rtype='blade', angle=angle_center)
            game.particles.append(blade_particle)
            blade_particle.game = game

            # Damage enemies in arc
            # Damage enemies inside the particle's radius
        def fist_blast(player, game):
            if player.mana < 5 or not game.room.enemies: return
            player.mana -= 5
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            ang = math.atan2(target.y - player.y, target.x - player.x)
            game.spawn_projectile(player.x, player.y, ang, 6, 1.0, 8, 'red', player.atk*2, stype='slash2')
        def chain_lightning(player, game):
            if player.mana < 5 or not game.room.enemies: return
            player.mana -= 5
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            ang = math.atan2(target.y - player.y, target.x - player.x)
            game.spawn_projectile(player.x, player.y, ang, 10, 20, 10,
                      'yellow', player.mag*2,
                      owner='player', stype='lightning', ptype='chain')

        def shadow_dagger(player, game):
            if player.mana < 5 or not game.room.enemies: return
            player.mana -= 5
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            ang = math.atan2(target.y - player.y, target.x - player.x)
            game.spawn_projectile(player.x, player.y, ang, 6, 3, 8, 'purple', player.mag*3, owner='player', stype='dagger')

        def fireball(player, game):
            if player.mana < 15 or not game.room.enemies: return
            player.mana -= 15
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            ang = math.atan2(target.y - player.y, target.x - player.x)
            game.spawn_projectile(player.x, player.y, ang, 8, 10, 10, 'orange', 50, 'player', ptype='fireball')

        def icicle(player, game):
            if player.mana < 15 or not game.room.enemies: return
            player.mana -= 15
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            ang = math.atan2(target.y - player.y, target.x - player.x)
            game.spawn_projectile(player.x, player.y, ang, 8, 10, 10, 'cyan', player.mag, 'player', ptype='icicle', stype='bolt1')


        def ice_shard(player, game):
            if player.mana < 15 or not game.room.enemies: return
            player.mana -= 15
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            ang = math.atan2(target.y - player.y, target.x - player.x)
            game.spawn_projectile(player.x, player.y, ang, 6, 3, 8, 'cyan', player.mag*10)

        def mana_bolt(player, game):
            if player.mana < 3 or not game.room.enemies: return
            player.mana -= 3
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            ang = math.atan2(target.y - player.y, target.x - player.x)
            game.spawn_projectile(player.x, player.y, ang, 6, 3, 8, 'cyan', player.mag*3, owner='player', stype='bolt1')
        def light_bolt(player, game):
            if player.mana < 3 or not game.room.enemies: return
            player.mana -= 3
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            ang = math.atan2(target.y - player.y, target.x - player.x)
            game.spawn_projectile(player.x, player.y, ang, 15, 3, 8, 'yellow', player.mag*2, owner='player', stype='bolt1')
        def arrow_shot(player, game):
            if player.mana < 1 or not game.room.enemies: return
            player.mana -= 1
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            ang = math.atan2(target.y - player.y, target.x - player.x)
            game.spawn_projectile(player.x, player.y, ang, 6, 3, 8, 'brown', player.atk*2, owner='player', stype='arrow')
        def chi_blast(player, game):
            if player.hp < 5 or not game.room.enemies: 
                return

            player.hp -= 5
            # Helper function to spawn a bolt
            def spawn_bolt():
                target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
                ang = math.atan2(target.y - player.y, target.x - player.x)
                game.spawn_projectile(player.x, player.y, ang, 6, 3, 8, 'cyan', player.vit*2, owner='player', stype='bolt')

            # Shoot immediately
            spawn_bolt()

            # Schedule next two bolts after 0.5s and 1.0s
            game.after(500, spawn_bolt)   # 500 ms = 0.5 sec
            game.after(1000, spawn_bolt)  # 1000 ms = 1 sec


        def mana_shield(player, game):
            duration_ms = 5000   # 5 seconds
            tick_ms = 10         # update every 0.01s
            mana_cost_per_tick = 0.1

            def shield_tick():
                # stop if mana is gone or time expired
                if player.mana <= 0 or time.time() >= player._mana_shield_end:
                    player._mana_shield_active = False
                    return

                # drain mana
                player.mana -= mana_cost_per_tick

                # shield radius
                shield_radius = 40 + player.mag

                # spawn shield particle
                shield_particle = Particle(
                    player.x, player.y,
                    shield_radius,
                    'white',
                    life=0.1,
                    rtype="shield",
                    outline=True
                )
                game.particles.append(shield_particle)

                # push enemies away
                for e in game.room.enemies:
                    d = distance((player.x, player.y), (e.x, e.y))
                    min_dist = 40 + player.mag
                    if d < min_dist:
                        angle = math.atan2(e.y - player.y, e.x - player.x)
                        push_strength = (min_dist - d) * 2
                        e.x += math.cos(angle) * push_strength
                        e.y += math.sin(angle) * push_strength

                # delete projectiles that hit the shield
                for proj in list(game.projectiles):
                    d = distance((player.x, player.y), (proj.x, proj.y))
                    if d <= shield_radius + getattr(proj, "radius", 5):
                        game.projectiles.remove(proj)

                # always reschedule next tick
                game.after(tick_ms, shield_tick)

            # activate if not already active
            if not getattr(player, "_mana_shield_active", False):
                player._mana_shield_active = True
                player._mana_shield_end = time.time() + (duration_ms / 1000.0)
                shield_tick()


        def multishot(player, game):
            # Need at least 1 enemy
            if player.mana < 4 or not game.room.enemies: return
            player.mana -= 4
                

            # Pick up to 5 different enemies (closest first)
            enemies = sorted(
                game.room.enemies,
                key=lambda e: distance((player.x, player.y), (e.x, e.y))
            )[:3]

            # Fire an arrow at each target
            for enemy in enemies:
                ang = math.atan2(enemy.y - player.y, enemy.x - player.x)
                game.spawn_projectile(
                    player.x, player.y,
                    ang,
                    7,       # speed
                    3,       # life
                    8,       # radius
                    'brown', # color
                    player.atk * 2,  # damage
                    owner='player',
                    stype='arrow'
                )

        # Assign skills based on class
        self.skills.clear()
        if self.class_name=='Mage':
            self.skills.append({'skill': mana_bolt,'name':'Mana Bolt','key':1,'level':1,'cooldown':0.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': mana_shield,'name':'Mana Shield','key':0,'level':5,'cooldown':2,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': fireball,'name':'Fireball','key':0,'level':10,'cooldown':1.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': icicle,'name':'Icicle','key':0,'level':10,'cooldown':1.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': chain_lightning,'name':'Chain Lightning','key':0,'level':15,'cooldown':2,'last_used':0,'cooldown_mod':1.0})
        elif self.class_name=='Warrior':
            self.skills.append({'skill': strike,'name':'Strikes','key':1,'level':1,'cooldown':0.2,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': ground_pound,'name':'Ground Pound','key':0,'level':5,'cooldown':0.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': fist_blast,'name':'Fist Blast','key':0,'level':10,'cooldown':1,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': rapid_strike,'name':'Charge','key':0,'level':15,'cooldown':2,'last_used':0,'cooldown_mod':1.0})
        elif self.class_name=='Rogue':
            self.skills.append({'skill': dark_slash,'name':'Dark Slash','key':1,'level':1,'cooldown':0.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': shadow_dagger,'name':'Shadow Dagger','key':0,'level':5,'cooldown':0.2,'last_used':0,'cooldown_mod':1.0})
        elif self.class_name=='Cleric':
            self.skills.append({'skill': light_bolt,'name':'Light Bolt','key':1,'level':1,'cooldown':0.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': minor_heal,'name':'Minor Heal','key':0,'level':5,'cooldown':1,'last_used':0,'cooldown_mod':1.0})
        elif self.class_name=='Druid':
            self.skills.append({'skill': thorn_whip,'name':'Thorn Whip','key':1,'level':1,'cooldown':0.4,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': summon_wolf,'name':'Summon Wolf','key':0,'level':5,'cooldown':1,'last_used':0,'cooldown_mod':1.0})
        elif self.class_name=='Monk':
            self.skills.append({'skill': chi_strike,'name':'Chi Strike','key':1,'level':1,'cooldown':0.2,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': chi_blast,'name':'Chi Blast','key':0,'level':5,'cooldown':1.5,'last_used':0,'cooldown_mod':1.0})
        elif self.class_name=='Ranger':
            self.skills.append({'skill': arrow_shot,'name':'Arrow Shot','key':1,'level':1,'cooldown':0.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': multishot,'name':'Multishot','key':0,'level':5,'cooldown':1,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': fire_trap,'name':'Fire Trap','key':0,'level':10,'cooldown':1,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': frost_trap,'name':'Frost Trap','key':0,'level':10,'cooldown':1,'last_used':0,'cooldown_mod':1.0})


    def gain_xp(self, amount, game=None):
        self.xp += amount
        leveled = False
        levels_gained = 0

        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.level += 1
            levels_gained += 1
            self.stat_points += 2
            self.skill_points += 1
            self.xp_to_next = int(self.xp_to_next * 1.3)

            # Apply class growth
            growth = CLASS_STAT_GROWTH.get(self.class_name, {})
            for stat, value in growth.items():
                setattr(self, stat, getattr(self, stat) + value)

            leveled = True

        # Update player stats after leveling
        if leveled:
            self.update_stats()

            # Scale existing enemies in the current room once
            if game:
                for e in game.room.enemies:
                    if isinstance(e, (Enemy, Boss)):
                        e.scale_with_player(self.level)
                rescale_room_enemies(game.room, self.level)

        return leveled

    def unlock_skills(self):
        for sk in self.skills:
            if sk['level']<=self.level and sk not in self.unlocked_skills:
                if len(self.unlocked_skills)<MAX_SKILLS:
                    self.unlocked_skills.append(sk)

    def to_dict(self):
        return {
            "name": self.name,
            "class_name": self.class_name,
            "level": self.level,
            "xp": self.xp,
            "xp_to_next": self.xp_to_next,
            "stat_points": self.stat_points,
            "skill_points": self.skill_points,
            "strength": self.strength,
            "vitality": self.vitality,
            "agility": self.agility,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "will": self.will,
            "constitution": self.constitution,
            "hp": self.hp,
            "mana": self.mana,
            "unlocked_skills": [sk['name'] for sk in self.unlocked_skills],
            "active_skill_effects": self.active_skill_effects,
            "active_skills": [
                {"name": sk['name'], "key": sk['key'], "cooldown": sk['cooldown'], "last_used": sk['last_used']}
                for sk in self.unlocked_skills
            ]
        }

    @classmethod
    def from_dict(cls, data):
        p = cls(name=data.get('name','Hero'), class_name=data.get('class_name','Warrior'))
        # Set base stats
        for stat in ['strength','vitality','agility','intelligence','wisdom','will','constitution']:
            if stat in data:
                setattr(p, stat, data[stat])
        p.level = data.get('level',1)
        p.xp = data.get('xp',0)
        p.xp_to_next = data.get('xp_to_next',100)
        p.stat_points = data.get('stat_points',5)
        p.skill_points = data.get('skill_points',0)
        p.update_stats()
        # Re-populate skills
        p.populate_skills()
        p.active_skill_effects = data.get('active_skill_effects', {})
        # Unlock the saved skills by name
        saved_skills = data.get('unlocked_skills',[])
        for sk in p.skills:
            if sk['name'] in saved_skills:
                p.unlocked_skills.append(sk)
        active_data = data.get("active_skills", [])
        for active in active_data:
            for sk in p.unlocked_skills:
                if sk['name'] == active['name']:
                    sk['key'] = active.get('key', sk['key'])
                    sk['cooldown'] = active.get('cooldown', sk['cooldown'])
                    sk['last_used'] = active.get('last_used', sk['last_used'])
        p.hp = min(data.get('hp', p.max_hp), p.max_hp)
        p.mana = min(data.get('mana', p.max_mana), p.max_mana)
        p.hp = p.max_hp
        p.mana = p.max_mana
        return p
    def reset(self):
        """Reset character to level 1 and base stats."""
        # Reset core stats
        self.level = 1
        self.xp = 0
        self.xp_to_next = 100
        self.stat_points = 5
        self.skill_points = 0

        # Base stats
        base_stats = {'strength':5, 'vitality':5, 'agility':5, 'intelligence':5,
                      'wisdom':5, 'will':5, 'constitution':3}
        for stat, val in base_stats.items():
            setattr(self, stat, val)

        # Clear skills and repopulate for class
        self.skills.clear()
        self.unlocked_skills.clear()
        self.populate_skills()
        self.unlock_skills()

        # Reset HP/Mana
        self.update_stats()
        self.hp = self.max_hp
        self.mana = self.max_mana
# ---------- Enemy/Boss/Projectile/Particle ----------
class Summoned:
    def __init__(self, name, hp, atk, spd, x, y, duration=10.0, role="loyal", owner=None, mana_upkeep=0.0):
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.atk = atk
        self.spd = spd
        self.x = x
        self.y = y
        self.size = 14
        self.role = role
        self.owner = owner        # reference to player or caster
        self.spawn_time = time.time()
        self.duration = duration  # how long it lasts
        self.state = "follow"     # default behavior
        self.attack_range = 40
        self.last_attack = 0
        self.attack_cooldown = 1.0
        self.room_row = y // ROOM_H
        self.room_col = x // ROOM_W
        self.skills = []
        self.mana_upkeep = mana_upkeep# list of skill dicts, same format as player


    def update(self, game, dt):
        # expire after duration
        if time.time() - self.spawn_time > self.duration:
            if self in game.summons:
                game.summons.remove(self)
            return
        if self.owner:
            # drain mana proportional to dt
            self.owner.mana -= self.mana_upkeep * dt
            if self.owner.mana <= 0:
                # despawn if player runs out
                if self in game.summons:
                    game.summons.remove(self)
                return
        player = game.player if self.owner is None else self.owner

        # --- Movement & attack based on role ---
        if self.role == "loyal":
            # Always stick close to player
            dx, dy = player.x - self.x, player.y - self.y
            dist = math.hypot(dx, dy)
            if dist > 30:
                ang = math.atan2(dy, dx)
                self.x += math.cos(ang) * self.spd
                self.y += math.sin(ang) * self.spd

            # Loyal skill usage: very short range
            for sk in self.skills:
                if time.time() - sk['last_used'] >= sk['cooldown']:
                    for e in game.room.enemies:
                        if distance((player.x, player.y), (e.x, e.y)) < 500:
                            sk['skill'](self, game)
                            sk['last_used'] = time.time()
                            break

        elif self.role == "defense":
            # Stay near player, wider radius
            dx, dy = player.x - self.x, player.y - self.y
            dist = math.hypot(dx, dy)
            if dist > 60:
                ang = math.atan2(dy, dx)
                self.x += math.cos(ang) * self.spd
                self.y += math.sin(ang) * self.spd

            # Attack enemies that approach player
            for e in game.room.enemies:
                if distance((player.x, player.y), (e.x, e.y)) < 80 and time.time() - self.last_attack >= self.attack_cooldown:
                    game.damage_enemy(e, self.atk)
                    self.last_attack = time.time()

            # Defense skill usage: medium range
            for sk in self.skills:
                if time.time() - sk['last_used'] >= sk['cooldown']:
                    for e in game.room.enemies:
                        if distance((player.x, player.y), (e.x, e.y)) < 100:
                            sk['skill'](self, game)
                            sk['last_used'] = time.time()
                            break

        elif self.role == "attack":
            if game.room.enemies:
                # Chase nearest enemy
                target = min(game.room.enemies, key=lambda e: distance((self.x, self.y), (e.x, e.y)))
                dx, dy = target.x - self.x, target.y - self.y
                dist = math.hypot(dx, dy)
                if dist > self.attack_range:
                    ang = math.atan2(dy, dx)
                    self.x += math.cos(ang) * self.spd
                    self.y += math.sin(ang) * self.spd
                elif time.time() - self.last_attack >= self.attack_cooldown:
                    game.damage_enemy(target, self.atk)
                    self.last_attack = time.time()

                # Attack skill usage: long range, anywhere in room
                for sk in self.skills:
                    if time.time() - sk['last_used'] >= sk['cooldown']:
                        sk['skill'](self, game)
                        sk['last_used'] = time.time()
            else:
                # No enemies → follow player
                dx, dy = player.x - self.x, player.y - self.y
                dist = math.hypot(dx, dy)
                if dist > 50:
                    ang = math.atan2(dy, dx)
                    self.x += math.cos(ang) * self.spd
                    self.y += math.sin(ang) * self.spd

        else:
            # Default "melee" role
            dx, dy = player.x - self.x, player.y - self.y
            dist = math.hypot(dx, dy)
            if dist > 50:
                ang = math.atan2(dy, dx)
                self.x += math.cos(ang) * self.spd
                self.y += math.sin(ang) * self.spd

            if game.room.enemies:
                target = min(game.room.enemies, key=lambda e: distance((self.x, self.y), (e.x, e.y)))
                d = distance((self.x, self.y), (target.x, target.y))
                if d <= self.attack_range and time.time() - self.last_attack >= self.attack_cooldown:
                    game.damage_enemy(target, self.atk)
                    self.last_attack = time.time()




    def draw(self, canvas):
        # simple circle for summon
        canvas.create_oval(
            self.x - self.size, self.y - self.size,
            self.x + self.size, self.y + self.size,
            fill="lightblue"
        )
        canvas.create_text(self.x, self.y - self.size - 10, text=self.name, fill="white")

class Enemy:
    def __init__(self, name, hp, atk, spd, x, y, role="melee", skills=None):
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.atk = atk
        self.spd = spd
        self.base_spd = self.spd
        self.x = x
        self.y = y
        self.size = 16
        self.state = 'wander'
        self.wander_target = (x, y)
        self.last_move = time.time()
        self.attack_range = 50
        self.role = role 
        self.skills = skills or []  # list of dicts: {'skill':func,'cooldown':num,'last_used':time}
        self.attack_cooldown = 1.0
        self.last_attack = 0
        self.room_row = y // ROOM_H
        self.room_col = x // ROOM_W
    def dodge_projectiles(self, game):
        for proj in game.projectiles:
            if proj.owner == "player":
                d = distance((self.x, self.y), (proj.x, proj.y))
                if d < 60:
                    ang = proj.angle
                    dodge_ang = ang + random.choice([-math.pi/2, math.pi/2])
                    self.x += math.cos(dodge_ang) * self.spd * 10
                    self.y += math.sin(dodge_ang) * self.spd * 10


    # Add this method to your Enemy class
    def scale_with_player(self, player_level):
        scale_factor = 1 + player_level * 0.2
        self.max_hp = int(self.max_hp * scale_factor)
        self.hp = min(self.hp, self.max_hp)
        self.atk = int(self.atk * scale_factor)
        self.spd = self.spd * (1 + player_level * 0.02)
    def update(self, game):
        now = time.time()
        player = game.player
        self.spd = self.base_spd
        for part in game.particles:
            if part.rtype == "frost":  # use your existing frost particles
                if distance((self.x, self.y), (part.x, part.y)) <= part.size:
                    self.spd = self.base_spd * 0.001   # 60% slow
                    break
        # --- compute once per frame ---
        d = distance((self.x, self.y), (player.x, player.y))
        for sk in self.skills:
            if sk["skill"].__name__ == "dash_attack":
                if d > 100 and time.time() - sk["last_used"] >= sk["cooldown"]:
                    sk["skill"](self, game)
                    sk["last_used"] = time.time()
                    return  # skip normal movement this frame
        # --- smarter dodge: only occasionally, and weaker ---
        if hasattr(self, "_last_dodge_time"):
            can_dodge = (now - self._last_dodge_time) > 0.2
        else:
            self._last_dodge_time = 0
            can_dodge = True

        if can_dodge:
            for proj in game.projectiles:
                if proj.owner == "player":
                    pd = distance((self.x, self.y), (proj.x, proj.y))
                    if pd < 100:
                        dodge_ang = proj.angle + random.choice([-math.pi/2, math.pi/2])
                        self.x += math.cos(dodge_ang) * (self.spd * 3)
                        self.y += math.sin(dodge_ang) * (self.spd * 3)
                        self._last_dodge_time = now
                        break

        # --- role-based movement ---
        if self.role == "melee":
            if self.hp <= self.max_hp / 2:
                # retreat
                ang = math.atan2(self.y - player.y, self.x - player.x)
                self.x += math.cos(ang) * (self.spd)
                self.y += math.sin(ang) * (self.spd)
                for sk in self.skills:
                    if sk.get("name") == "Self Heal" and now - sk.get("last_used", 0) >= sk.get("cooldown", 1):
                        sk["skill"](self, game)
                        sk["last_used"] = now
                        break
            else:
                # chase until close
                if d > self.attack_range:
                    ang = math.atan2(player.y - self.y, player.x - self.x)
                    self.x += math.cos(ang) * self.spd
                    self.y += math.sin(ang) * self.spd

            # attack if in range
            if d <= self.attack_range:
                usable = [
                    sk for sk in self.skills
                    if "melee" in sk.get("tags", [])   # only melee skills
                    and now - sk.get("last_used", 0) >= sk.get("cooldown", 1)
                ]
                if usable:
                    chosen = random.choice(usable)
                    chosen["skill"](self, game)
                    chosen["last_used"] = now

        elif self.role in ("ranged", "magic", "support"):
            desired_range = self.attack_range + 750  # preferred spacing
            if d < desired_range:  # too close → back away
                ang = math.atan2(self.y - player.y, self.x - player.x)
                self.x += math.cos(ang) * self.spd
                self.y += math.sin(ang) * self.spd
            elif d > desired_range:  # too far → move closer
                ang = math.atan2(player.y - self.y, player.x - self.x)
                self.x += math.cos(ang) * self.spd
                self.y += math.sin(ang) * self.spd

            # attack with skills
            usable = [sk for sk in self.skills if now - sk.get("last_used", 0) >= sk.get("cooldown", 1)]
            if usable:
                chosen = random.choice(usable)
                chosen["skill"](self, game)
                chosen["last_used"] = now

            # shield if half health
            if self.hp <= self.max_hp / 2:
                for sk in self.skills:
                    if sk.get("name") == "Shield" and now - sk.get("last_used", 0) >= sk.get("cooldown", 1):
                        sk["skill"](self, game)
                        sk["last_used"] = now
                        break
        else:
            # FALLBACK: If role doesn't match anything, just chase the player
            if d > 50:
                ang = math.atan2(player.y - self.y, player.x - self.x)
                self.x += math.cos(ang) * self.spd
                self.y += math.sin(ang) * self.spd

        # --- clamp to WINDOW boundaries (not room boundaries) ---
        self.x = clamp(self.x, self.size, WINDOW_W - self.size)
        self.y = clamp(self.y, self.size, WINDOW_H - self.size)


    def gain_xp(self, amount, game=None):
        self.xp += amount
        leveled = False
        while self.xp >= self.xp_to_next:
            self.xp -= self.xp_to_next
            self.level += 1
            self.stat_points += 2
            self.skill_points += 1
            self.xp_to_next = int(self.xp_to_next * 1.3)
            leveled = True
            growth = CLASS_STAT_GROWTH.get(self.class_name, {})
            for stat, value in growth.items():
                setattr(self, stat, getattr(self, stat) + value)

        self.update_stats()

        # Scale current enemies if game instance is passed
        if leveled and game:
            for e in game.room.enemies:
                if isinstance(e, Enemy):
                    e.scale_with_player(self.level)

        return leveled

def shield(caster, game):
    # Cooldown check
    if time.time() - getattr(caster, "last_shield", 0) < 5:  # 5s cooldown
        return

    caster.last_shield = time.time()

    # Shield parameters
    shield_radius = 40 + caster.atk   # scale with caster’s attack or magic
    duration = 3.0                    # shield lasts 3 seconds
    tick_ms = 100                     # update every 0.1s

    def shield_tick():
        # expire if duration passed
        if time.time() >= caster._shield_end:
            caster._shield_active = False
            return

        # spawn shield particle
        shield_particle = Particle(
            caster.x, caster.y,
            shield_radius,
            "blue",
            life=0.2,
            rtype="shield",
            outline=True
        )
        game.particles.append(shield_particle)

        # block projectiles
        for proj in list(game.projectiles):
            d = distance((caster.x, caster.y), (proj.x, proj.y))
            if d <= shield_radius + getattr(proj, "radius", 5):
                game.projectiles.remove(proj)

        # optional: push enemies away if caster is a boss
        if isinstance(caster, Enemy):
            for e in list(game.room.enemies):
                if e is not caster:
                    d = distance((caster.x, caster.y), (e.x, e.y))
                    if d < shield_radius:
                        ang = math.atan2(e.y - caster.y, e.x - caster.x)
                        push_strength = (shield_radius - d) * 0.5
                        e.x += math.cos(ang) * push_strength
                        e.y += math.sin(ang) * push_strength

        # reschedule tick
        game.after(tick_ms, shield_tick)

    # activate shield
    if not getattr(caster, "_shield_active", False):
        caster._shield_active = True
        caster._shield_end = time.time() + duration
        shield_tick()

# Enemy skills
def claw_slash(enemy, game):
    # Deals melee damage in a small radius with swipe effect
    arc_radius = 40
    num_particles = 8
    angle_center = math.atan2(game.player.y - enemy.y, game.player.x - enemy.x)
    arc_width = math.pi / 2
    for i in range(num_particles):
        angle = angle_center - arc_width/2 + (i / (num_particles-1)) * arc_width
        x = enemy.x + math.cos(angle) * arc_radius * random.uniform(0.8, 1.2)
        y = enemy.y + math.sin(angle) * arc_radius * random.uniform(0.8, 1.2)
        game.spawn_particle(x, y, random.uniform(5,10), 'green')
    # Deal damage to player if in arc
    if distance((enemy.x, enemy.y), (game.player.x, game.player.y)) <= arc_radius:
        game.damage_player(enemy.atk * 1.5)
def fire_slash(enemy, game):
    # Deals melee damage in a small radius with swipe effect
    arc_radius = 40
    num_particles = 16
    angle_center = math.atan2(game.player.y - enemy.y, game.player.x - enemy.x)
    arc_width = math.pi / 2
    for i in range(num_particles):
        angle = angle_center - arc_width/2 + (i / (num_particles-1)) * arc_width
        x = enemy.x + math.cos(angle) * arc_radius * random.uniform(0.8, 1.2)
        y = enemy.y + math.sin(angle) * arc_radius * random.uniform(0.8, 1.2)
        game.spawn_particle(x, y, random.uniform(5,10), 'orange', owner="enemy", rtype="flame")
    # Deal damage to player if in arc
    if distance((enemy.x, enemy.y), (game.player.x, game.player.y)) <= arc_radius:
        game.damage_player(enemy.atk * 1.5)

def fire_spit(enemy, game):
    ang = math.atan2(game.player.y - enemy.y, game.player.x - enemy.x)
    # Add flame particles along path
    for _ in range(5):
        px = enemy.x + random.uniform(-5,5)
        py = enemy.y + random.uniform(-5,5)
        game.spawn_particle(px, py, random.uniform(3,6), 'orange')
    game.spawn_projectile(enemy.x, enemy.y, ang, 6, 2, 15, 'orange', enemy.atk * 2, 'enemy')


def poison_cloud(enemy, game):
    radius = 50 + enemy.atk
    num_particles = 15
    for _ in range(num_particles):
        x = enemy.x + random.uniform(-radius, radius)
        y = enemy.y + random.uniform(-radius, radius)
        game.spawn_particle(x, y, random.uniform(4,8), 'green')
    if distance((enemy.x, enemy.y), (game.player.x, game.player.y)) <= radius:
        game.damage_player(enemy.atk * 2)

def dark_bolt(enemy, game):
    # Ranged rock projectile
    ang = math.atan2(game.player.y - enemy.y, game.player.x - enemy.x)
    game.spawn_projectile(enemy.x, enemy.y, ang, 20, 2.5, 10, 'purple', enemy.atk * 2, 'enemy', stype="bolt1")

def life_bolt(enemy, game):
    # If no enemies, do nothing
    if not game.room.enemies:
        return

    # Find enemy that lost the MOST health
    target = max(
        game.room.enemies,
        key=lambda e: (e.max_hp - e.hp)
    )

    # Compute angle toward that enemy
    ang = math.atan2(target.y - enemy.y, target.x - enemy.x)

    # Spawn projectile owned by enemy
    # damage value will be used as "healing"
    game.spawn_projectile(
        enemy.x, enemy.y,
        ang,                # angle toward the target
        20,                 # speed
        2.5,                # life
        10,                 # radius
        'yellow',           # color
        enemy.atk * 3,      # heal amount
        'enemy_lifebolt'    # special owner type
    )

def ice_blast(enemy, game):
    radius = 60
    num_shards = 8
    for i in range(num_shards):
        angle = (i / num_shards) * 2 * math.pi
        x = enemy.x + math.cos(angle) * radius
        y = enemy.y + math.sin(angle) * radius
        game.spawn_particle(x, y, random.uniform(3,6), 'cyan', '0.2')
    if distance((enemy.x, enemy.y), (game.player.x, game.player.y)) <= radius:
        game.damage_player(enemy.atk)
        if hasattr(game.player, 'speed'):
            game.player.speed *= 0.7

def summon_minion(enemy, game):
    minionR = 0
    # Spawns a weak minion nearby
    x = enemy.x + random.randint(-30, 30)
    y = enemy.y + random.randint(-30, 30)
    minion = Enemy("Minion", 30, 4, 1.2, x, y)

    game.room.enemies.append(minion)

def dash_strike(enemy, game):
    """Enhanced dash skill: faster, more damage, and adds visual effect."""
    ang = math.atan2(game.player.y - enemy.y, game.player.x - enemy.x)
    
    # Dash movement: double speed
    dash_distance = enemy.spd * 20  # faster than normal
    enemy.x += math.cos(ang) * dash_distance
    enemy.y += math.sin(ang) * dash_distance

    # Visual effect: spawn trailing particles
    for _ in range(8):
        offset_x = enemy.x + random.uniform(-5, 5)
        offset_y = enemy.y + random.uniform(-5, 5)
        size = random.uniform(10, 10)
        game.spawn_particle(offset_x, offset_y, size, 'green')  # can be customized

    # Attack damage
    if distance((enemy.x, enemy.y), (game.player.x, game.player.y)) <= 25:
        damage = enemy.atk * 2.5  # stronger than before
        game.damage_player(damage)

def rock_throw(enemy, game):
    # Ranged rock projectile
    ang = math.atan2(game.player.y - enemy.y, game.player.x - enemy.x)
    game.spawn_projectile(enemy.x, enemy.y, ang, 10, 10, 30, 'brown', enemy.atk * 1.5, 'enemy')

def self_heal(enemy, game):
    """Heals the enemy with a visual particle effect."""
    heal_amount = enemy.atk * 2
    enemy.hp = min(enemy.max_hp, enemy.hp + heal_amount)

    # Spawn a burst of green particles around the enemy
    num_particles = 4
    radius = 0.5
    for _ in range(num_particles):
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(0, radius)
        x = enemy.x + math.cos(angle) * dist
        y = enemy.y + math.sin(angle) * dist
        size = random.uniform(5, 10)
        game.spawn_particle(x, y, size, 'green',  rtype="diamond")
# Enemy version of Strike
def enemy_strike(enemy, game):
    if not game.player: 
        return
    # Same mana check replaced with cooldown logic (enemies don’t use mana)
    arc_radius = 30
    arc_width = math.pi / 3
    px, py = enemy.x, enemy.y

    # Angle toward player
    angle_center = math.atan2(game.player.y - py, game.player.x - px)

    # Spawn blade particle
    offset = arc_radius // 2
    spawn_x = px + math.cos(angle_center) * offset
    spawn_y = py + math.sin(angle_center) * offset
    blade_particle = Particle(spawn_x, spawn_y, arc_radius, 'gray', life=0.3, rtype='eblade1', angle=angle_center, damage=enemy.atk*1.5)
    game.particles.append(blade_particle)

    # Damage player if inside arc
    dx, dy = game.player.x - px, game.player.y - py
    dist = math.hypot(dx, dy)
    if dist <= arc_radius:
        angle_to_player = math.atan2(dy, dx)
        diff = (angle_to_player - angle_center + math.pi*2) % (math.pi*2)
        if diff < arc_width/2 or diff > math.pi*2 - arc_width/2:
            game.damage_player(enemy.atk)
def dash_attack(enemy, game):
    # cooldown check
    if time.time() - enemy.last_attack < enemy.attack_cooldown:
        return

    # dash parameters
    dash_distance = 80
    dash_speed = 12
    target = game.player
    ang = math.atan2(target.y - enemy.y, target.x - enemy.x)

    # move enemy forward quickly
    enemy.x += math.cos(ang) * dash_distance
    enemy.y += math.sin(ang) * dash_distance

    # optional: damage if close enough after dash
    if distance((enemy.x, enemy.y), (target.x, target.y)) <= enemy.attack_range:
        game.damage_enemy(target, enemy.atk * 2)  # stronger hit

    enemy.last_attack = time.time()

# Enemy version of Dark Slash
def enemy_dark_slash(enemy, game):
    if not game.player:
        return
    arc_radius = 40
    arc_width = math.pi / 3
    px, py = enemy.x, enemy.y
    angle_center = math.atan2(game.player.y - py, game.player.x - px)
    offset = 40 // 2
    spawn_x = px + math.cos(angle_center) * offset
    spawn_y = py + math.sin(angle_center) * offset
    blade_particle = Particle(px, py, arc_radius, 'grey', life=0.3, rtype='eblade', angle=angle_center, damage=enemy.atk)
    game.particles.append(blade_particle)

    dx, dy = game.player.x - px, game.player.y - py
    dist = math.hypot(dx, dy)
    if dist <= arc_radius:
        angle_to_player = math.atan2(dy, dx)
        diff = (angle_to_player - angle_center + math.pi*2) % (math.pi*2)
        if diff < arc_width/2 or diff > math.pi*2 - arc_width/2:
            game.damage_player(enemy.atk * 1.5)

# Enemy version of Arrow Shot
def enemy_arrow_shot(enemy, game):
    if not game.player:
        return
    ang = math.atan2(game.player.y - enemy.y, game.player.x - enemy.x)
    game.spawn_projectile(
        enemy.x, enemy.y,
        ang,
        6, 3, 8,
        'brown',
        enemy.atk * 2,
        owner='enemy',
        stype='arrow'
    )

def create_enemy_types_by_dungeon():
    return {
        1: [  # Dungeon 1: Forest
            lambda x, y: Enemy(
                "Swordman", 60, 5, 3, x, y, role="melee",
                skills=[
                    {"skill": enemy_dark_slash, "name": "Arc Slash", "tags": ["melee"], "cooldown": 1.5, "last_used": 0},
                    {"skill": self_heal, "name": "Self Heal", "tags": ["magic"], "cooldown": 1.5, "last_used": 0}
                ]
            ),
            lambda x, y: Enemy(
                "Spearman", 50, 5, 3, x, y, role="melee",
                skills=[
                    {"skill": enemy_strike, "name": "Strike", "tags": ["melee"], "cooldown": 0.5, "last_used": 0},
                    {"skill": dash_attack, "name": "Dash", "tags": ["support"], "cooldown": 2.0, "last_used": 0},
                    {"skill": self_heal, "name": "Self Heal", "tags": ["magic"], "cooldown": 1.5, "last_used": 0}
                    
                ]
            ),
            lambda x, y: Enemy(
                "Archer", 35, 6, 2.0, x, y, role="ranged",  # Changed from 3.0 to 2.0 for better ranged behavior
                skills=[
                    {"skill": enemy_arrow_shot, "name": "Arrow Shot", "tags": ["ranged"], "cooldown": 1.0, "last_used": 0}
                ]
            ),
        ],
        2: [  # Dungeon 2: Volcano
            lambda x, y: Enemy(
                "Fire Imp", 35, 8, 4.0, x, y, role="melee",
                skills=[
                    {"skill": fire_slash, "name": "Fire Slash", "tags": ["melee"], "cooldown": 1.0, "last_used": 0}
                ]
            ),
            lambda x, y: Enemy(
                "Flame Elemental", 50, 8, 1.5, x, y, role="magic",
                skills=[
                    {"skill": fire_spit, "name": "Fire Spit", "tags": ["magic"], "cooldown": 2.0, "last_used": 0}
                ]
            ),
            lambda x, y: Enemy(
                "Troll", 100, 12, 0.8, x, y, role="magic",
                skills=[
                    {"skill": rock_throw, "name": "Rock Throw", "tags": ["melee"], "cooldown": 5.0, "last_used": 0},
                    {"skill": self_heal, "name": "Self Heal", "tags": ["support"], "cooldown": 2.0, "last_used": 0}
                ]
            ),
        ],

        3: [  # Dungeon 3: Ice Cavern
            lambda x, y: Enemy(
                "Ice Golem", 100, 10, 0.6, x, y, role="melee",
                skills=[
                    {"skill": ice_blast, "name": "Ice Blast", "tags": ["melee"], "cooldown": 3.0, "last_used": 0}
                ]
            ),
            lambda x, y: Enemy(
                "Dark Mage", 40, 7, 1.2, x, y, role="magic",
                skills=[
                    {"skill": dark_bolt, "name": "Dark Bolt", "tags": ["magic"], "cooldown": 2.0, "last_used": 0},
                    {"skill": ice_blast, "name": "Ice Blast", "tags": ["magic"], "cooldown": 3.0, "last_used": 0},
                    {"skill": shield, "name": "Shield", "tags": ["magic"], "cooldown": 3.0, "last_used": 0}
                    
                ]
            ),
        ],

        4: [  # Dungeon 4: Shadow Realm
            lambda x, y: Enemy(
                "Summoner", 50, 5, 1.0, x, y, role="magic",
                skills=[
                    {"skill": dark_bolt, "name": "Dark Bolt", "tags": ["magic"], "cooldown": 0.9, "last_used": 0},
                    {"skill": summon_minion, "name": "Summon Minion", "tags": ["support"], "cooldown": 9.0, "last_used": 0}
                ]
            ),
            lambda x, y: Enemy(
                "Healer", 50, 8, 1.5, x, y, role="support",
                skills=[
                    {"skill": life_bolt, "name": "Life Bolt", "tags": ["support"], "cooldown": 0.7, "last_used": 0}
                ]
            ),
            lambda x, y: Enemy(
                "Venom Lurker", 30, 10, 4.0, x, y, role="melee",
                skills=[
                    {"skill": poison_cloud, "name": "Poison Cloud", "tags": ["melee"], "cooldown": 0.3, "last_used": 0},
                    {"skill": dash_strike, "name": "Dash Strike", "tags": ["melee"], "cooldown": 2.0, "last_used": 0}
                ]
            ),
        ],
    }


def spawn_enemies_for_dungeon(room, dungeon_id, player_level, count=6):
    enemy_pools = create_enemy_types_by_dungeon()
    pool = enemy_pools.get(dungeon_id, [])
    for _ in range(count):
        if not pool:
            break
        et = random.choice(pool)
        x = random.randint(50, WINDOW_W - 50)
        y = random.randint(50, WINDOW_H - 50)
        enemy = et(x, y)

        # Scale stats with player level
        scale_factor = 1 + player_level * 0.2
        enemy.max_hp = int(enemy.max_hp * scale_factor)
        enemy.hp = enemy.max_hp
        enemy.atk = int(enemy.atk * scale_factor)
        enemy.spd *= (1 + player_level * 0.02)

        room.enemies.append(enemy)



class Boss(Enemy):
    def __init__(self, name, x, y, boss_type='Generic', max_hp=500, atk=15, speed=1.2):
        super().__init__(name, max_hp, atk, speed, x, y)
        self.boss_type = boss_type
        self.size = 30
        self.color = 'orange'
        self.skills = []
        self.last_used_skill_time = {}
        self.init_by_type()

    def scale_with_player(self, player_level):
        scale_factor = 1 + player_level * 0.5  # Bosses scale slightly faster
        self.max_hp = int(self.max_hp * scale_factor)
        self.hp = min(self.hp, self.max_hp)
        self.atk = int(self.atk * scale_factor)
        self.spd = self.spd * (1 + player_level * 0.03)
    def init_by_type(self):
        """Assign stats and skills based on boss type"""
        if self.boss_type == 'FireLord':
            self.max_hp += 600
            self.hp = self.max_hp
            self.atk += 40
            self.size = 20
            self.fire_rate = 1.5
            self.skills = [
                {'skill': self.fireball_attack, 'cooldown': 2},
                {'skill': self.flame_wave, 'cooldown': 4},
                {'skill': self.heal, 'cooldown': 3}
            ]
        elif self.boss_type == 'IceGiant':
            self.max_hp += 800
            self.hp = self.max_hp
            self.atk += 60
            self.size = 25
            self.skills = [
                {'skill': self.ice_shard_attack, 'cooldown': 2},
                {'skill': self.freeze_aura, 'cooldown': 4},
                {'skill': self.heal, 'cooldown': 3}
            ]
        elif self.boss_type == 'ShadowWraith':
            self.max_hp += 500
            self.hp = self.max_hp
            self.atk += 60
            self.size = 10
            self.spd = 9
            self.skills = [
                {'skill': self.direball, 'cooldown': 2},
                {'skill': self.arcane_storm, 'cooldown': 4},
                {'skill': self.heal, 'cooldown': 3}
            ]
        elif self.boss_type == 'EarthTitan':
            self.max_hp += 900
            self.hp = self.max_hp
            self.atk += 80
            self.size = 30
            self.skills = [
                {'skill': self.rock_throw, 'cooldown': 3},
                {'skill': self.boss_shockwave, 'cooldown': 2},
                {'skill': self.heal, 'cooldown': 3}
            ]
    # ---------- Example Skills ----------
    def fireball_attack(self, game):
        """Shoots a spread of fireballs"""
        player = game.player
        ang = math.atan2(player.y - self.y, player.x - self.x)
        for delta in [-0.2, 0, 0.2]:
            game.spawn_projectile(self.x, self.y, ang + delta, 6, 3, 10, 'orange', self.atk*10, 'enemy')
    def direball(self, game):
        """Shoots a spread of fireballs"""
        player = game.player
        ang = math.atan2(player.y - self.y, player.x - self.x)
        for delta in [-0.2, 0, 0.2]:
            game.spawn_projectile(self.x, self.y, ang + delta, 6, 3, 20, 'purple', self.atk*5, 'enemy')
    def summon_minions(self, game):
        for _ in range(2):
            x = self.x + random.randint(-40, 40)
            y = self.y + random.randint(-40, 40)
            minion = Enemy("FlameElemental", 30, 5, 1.5, x, y)
            game.room.enemies.append(minion)
    def rock_throw(enemy, game):
        # Ranged rock projectile
        ang = math.atan2(game.player.y - enemy.y, game.player.x - enemy.x)
        game.spawn_projectile(enemy.x, enemy.y, ang, 10, 10, 40, 'brown', enemy.atk * 1.5, 'enemy')
    def boss_shockwave(boss, game):
        # Mana or cooldown check if needed
        # Shockwave parameters
        shockwave_radius = 30       # starting radius
        max_radius = 150            # how far the wave expands
        expansion_speed = 10        # pixels per frame
        damage = boss.atk * 2       # stronger than player’s version

        # Create a particle that represents the expanding ring
        shockwave = Particle(
            boss.x, boss.y,
            size=shockwave_radius,
            color='red',
            life=0.6,
            rtype='shockwave',
            outline=True
        )
        shockwave.expansion_speed = expansion_speed
        shockwave.max_radius = max_radius
        shockwave.damage = damage
        game.particles.append(shockwave)

        # Apply immediate damage + knockback to enemies in range (player + summons)
        targets = [game.player] + list(game.summons)
        for t in targets:
            d = distance((boss.x, boss.y), (t.x, t.y))
            if d < max_radius:
                game.damage_enemy(t, damage)  # or damage_player if you separate logic
                ang = math.atan2(t.y - boss.y, t.x - boss.x)
                push_strength = (max_radius - d) * 0.4
                t.x += math.cos(ang) * push_strength
                t.y += math.sin(ang) * push_strength

    def flame_wave(self, game):
        """AoE flame around boss"""
        for e in game.room.enemies:
            if e != self: continue
        for _ in range(50):
            x = self.x + random.uniform(-120,120)
            y = self.y + random.uniform(-120,120)
            game.spawn_particle(x, y, random.uniform(5,10), 'red',owner="enemy", rtype="flame")
        if distance((self.x,self.y),(game.player.x,game.player.y))<120:
            game.damage_player(self.atk*5)
    
    def ice_shard_attack(self, game):
        """Shoots shards in all directions"""
        num_shards = 8
        for i in range(num_shards):
            angle = i/num_shards*2*math.pi
            game.spawn_projectile(self.x, self.y, angle, 5, 2, 8, 'cyan', self.atk*5, 'enemy')

    def freeze_aura(self, game):
        """Slows player if nearby"""
        for _ in range(20):
            x = self.x + random.uniform(-120,120)
            y = self.y + random.uniform(-120,120)
            game.spawn_particle(x, y, random.uniform(5,10), 'cyan')
        if distance((self.x, self.y), (game.player.x, game.player.y)) < 80:
            game.player.speed *= 0.5
            game.spawn_particle(game.player.x, game.player.y, 15, 'blue')
    def heal(enemy, game):
        """Heals the enemy with a visual particle effect."""
        heal_amount = enemy.atk * 20
        enemy.hp = min(enemy.max_hp, enemy.hp + heal_amount)

        # Spawn a burst of green particles around the enemy
        num_particles = 12
        radius = enemy.size + 10
        for _ in range(num_particles):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(0, radius)
            x = enemy.x + math.cos(angle) * dist
            y = enemy.y + math.sin(angle) * dist
            size = random.uniform(5, 10)
            game.spawn_particle(x, y, size, 'yellow')

    def arcane_storm(self, game):
        player = game.player
        angle_center = math.atan2(player.y - self.y, player.x - self.x)
        num_proj = 10
        arc_width = math.pi / 2
        for i in range(num_proj):
            angle = angle_center - arc_width/2 + (i / (num_proj-1)) * arc_width
            game.spawn_projectile(self.x, self.y, angle, 5, 3, 8, 'purple', self.atk*10, 'enemy')

    def update(self, dt, game):
        """Move and use skills"""
        # Move towards player
        player = game.player
        ang = math.atan2(player.y - self.y, player.x - self.x)
        self.x += math.cos(ang) * self.spd
        self.y += math.sin(ang) * self.spd

        now = time.time()
        # Use skills
        for sk in self.skills:
            last_used = self.last_used_skill_time.get(sk['skill'], 0)
            if now - last_used >= sk['cooldown']:
                sk['skill'](game)
                self.last_used_skill_time[sk['skill']] = now
def spawn_boss_for_room(room, dungeon_id):
    boss_x, boss_y = WINDOW_W//2, WINDOW_H//2
    boss_types = {
        1: 'EarthTitan',
        2: 'FireLord',
        3: 'IceGiant',
        4: 'ShadowWraith'
    }
    boss_name = f"Dungeon {dungeon_id} Boss"
    boss_type = boss_types.get(dungeon_id, 'Generic')
    boss = Boss(boss_name, boss_x, boss_y, boss_type)
    room.enemies.append(boss)

class Projectile:
    def __init__(self,x,y,angle,speed,life,radius,color,damage,owner='player', ptype='normal', stype='basic'):
        self.x=x; self.y=y; self.angle=angle; self.speed=speed;
        self.life=life; self.radius=radius; self.color=color; self.damage=damage; self.owner=owner
        self.ptype = ptype; self.stype = stype;self.spawn_time = time.time();
        self.stopped = False   # NEW FLAG
    def update(self,dt,game):
        self.x += math.cos(self.angle)*self.speed
        self.y += math.sin(self.angle)*self.speed
        self.life -= dt
        if self.x<0 or self.x>WINDOW_W or self.y<0 or self.y>WINDOW_H: self.life=0; return
        if not self.stopped:
            self.x += math.cos(self.angle) * self.speed
            self.y += math.sin(self.angle) * self.speed
        # lifetime check
        if time.time() - self.spawn_time > self.life:
            self.alive = False

        if self.owner == 'summon' or self.owner == 'player':
            for e in list(game.room.enemies):
                if distance((self.x,self.y),(e.x,e.y))<=self.radius+e.size:
                    if self.stype == "howl":
                        angle_deg = math.degrees(self.angle) % 360
                        arc_extent = 60
                        thickness = 6

                        for i in range(3):
                            radius = self.radius * (i + 2)
                            self.canvas.create_arc(
                                self.x - radius, self.y - radius,
                                self.x + radius, self.y + radius,
                                start=angle_deg - arc_extent / 2,
                                extent=arc_extent,
                                style="arc",
                                outline=self.color,
                                width=thickness
                            )

                    elif self.ptype == 'fireball':
                        for e in list(game.room.enemies):
                            if distance((self.x, self.y), (e.x, e.y)) <= e.size + self.radius:
                                game.damage_enemy(e, self.damage)

                                # spawn scattered flame particles on impact
                                for _ in range(100):
                                    ang = random.uniform(0, 2 * math.pi)       # random angle
                                    r = random.uniform(0, 70)                  # random radius
                                    px = e.x + math.cos(ang) * r
                                    py = e.y + math.sin(ang) * r
                                    size = random.uniform(6, 12)
                                    flame = Particle(px, py, size, "orange", life=1, owner="player", rtype="flame")
                                    game.particles.append(flame)
                                # remove projectile after hit
                                if self in game.projectiles:
                                    game.projectiles.remove(self)
                                break
                    if self.ptype == 'icicle':
                        for e in list(game.room.enemies):
                            if distance((self.x, self.y), (e.x, e.y)) <= e.size + self.radius:
                                # direct hit damage
                                game.damage_enemy(e, self.damage)

                                # spawn scattered frost particles on impact
                                for _ in range(30):
                                    ang = random.uniform(0, 2 * math.pi)   # random angle
                                    r = random.uniform(0, 70)              # random radius
                                    px = e.x + math.cos(ang) * r
                                    py = e.y + math.sin(ang) * r
                                    size = random.randint(4, 8)           # varied snowflake size

                                    frost = game.spawn_particle(
                                        px, py,
                                        size,
                                        random.choice(["white", "cyan"]),  # flicker colors
                                        life=8,
                                        rtype="frost",
                                        owner="player"
                                    )
                                    game.particles.append(frost)

                                # remove projectile after hit
                                if self in game.projectiles:
                                    game.projectiles.remove(self)
                                break


                    if self.ptype == "chain":
                        game.damage_enemy(e,self.damage);
                        others = [enemy for enemy in game.room.enemies if enemy != e]
                        if others:
                            target = min(others, key=lambda en: distance((self.x, self.y), (en.x, en.y)))
                            ang = math.atan2(target.y - self.y, target.x - self.x)
                            game.spawn_projectile(self.x, self.y, ang,
                                                  self.speed, self.life, self.radius,
                                                  "yellow", self.damage,
                                                  owner=self.owner, stype="lightning", ptype="chain1")
                    if self.ptype == "chain1":
                        game.damage_enemy(e,self.damage);
                        others = [enemy for enemy in game.room.enemies if enemy != e]
                        if others:
                            target = min(others, key=lambda en: distance((self.x, self.y), (en.x, en.y)))
                            ang = math.atan2(target.y - self.y, target.x - self.x)
                            game.spawn_projectile(self.x, self.y, ang,
                                                  self.speed, self.life, self.radius,
                                                  "yellow", self.damage,
                                                  owner=self.owner, stype="lightning", ptype="chain2")
                    if self.ptype == "chain2":
                        game.damage_enemy(e,self.damage);
                        others = [enemy for enemy in game.room.enemies if enemy != e]
                        if others:
                            target = min(others, key=lambda en: distance((self.x, self.y), (en.x, en.y)))
                            ang = math.atan2(target.y - self.y, target.x - self.x)
                            game.spawn_projectile(self.x, self.y, ang,
                                                  self.speed, self.life, self.radius,
                                                  "yellow", self.damage,
                                                  owner=self.owner, stype="lightning", ptype="chain3")
                    if self.ptype == "chain3":
                        game.damage_enemy(e,self.damage);
                        others = [enemy for enemy in game.room.enemies if enemy != e]
                        if others:
                            target = min(others, key=lambda en: distance((self.x, self.y), (en.x, en.y)))
                            ang = math.atan2(target.y - self.y, target.x - self.x)
                            game.spawn_projectile(self.x, self.y, ang,
                                                  self.speed, self.life, self.radius,
                                                  "yellow", self.damage,
                                                  owner=self.owner, stype="lightning", ptype="chain4")
                    if self.ptype == "chain4":
                        game.damage_enemy(e,self.damage);
                        others = [enemy for enemy in game.room.enemies if enemy != e]
                        if others:
                            target = min(others, key=lambda en: distance((self.x, self.y), (en.x, en.y)))
                            ang = math.atan2(target.y - self.y, target.x - self.x)
                            game.spawn_projectile(self.x, self.y, ang,
                                                  self.speed, self.life, self.radius,
                                                  "yellow", self.damage,
                                                  owner=self.owner, stype="lightning")

                    else:
                        game.damage_enemy(e,self.damage); self.life=0; return
        elif self.owner=='enemy':
            p=game.player
            if distance((self.x,self.y),(p.x,p.y))<=self.radius+p.size:
                game.damage_player(self.damage); self.life=0; return
        elif self.owner == 'enemy_lifebolt':
            # home target = most injured enemy
            if game.room.enemies:
                target = max(
                    game.room.enemies,
                    key=lambda e: (e.max_hp - e.hp)
                )

                # Check collision with that target
                if distance((self.x, self.y), (target.x, target.y)) <= self.radius + target.size:
                    # Heal enemy instead of damage
                    target.hp = min(target.max_hp, target.hp + self.damage)
                    return
        def spawn_aoe_fire(self, game, target_enemy):
            """Spawn a big orange AoE circle at the enemy's position."""
            aoe_radius = 50  # size of explosion
            num_particles = 20

            # Damage all enemies in the AoE
            for e in list(game.room.enemies):
                if distance((target_enemy.x, target_enemy.y), (e.x, e.y)) <= aoe_radius:
                    game.damage_enemy(e, self.damage)

            # Spawn visual particles
            for _ in range(num_particles):
                angle = random.uniform(0, 2*math.pi)
                dist = random.uniform(0, aoe_radius)
                x = target_enemy.x + math.cos(angle) * dist
                y = target_enemy.y + math.sin(angle) * dist
                size = random.uniform(5, 15)
                game.spawn_particle(x, y, size, 'orange')

class Particle:
    def __init__(self, x, y, size, color, life=0.5, rtype='basic', atype=None, angle=0.0, outline=False, radius=0, owner=None, damage=0):
        self.x = x
        self.y = y
        self.size = size
        self.color = color
        self.life = float(life)   # ensure numeric
        self.rtype = rtype
        self.atype = atype
        self.outline = outline
        self.owner = owner# 'basic' or 'blade'
        self.angle = angle
        self.age = 0# direction (used for blade rotation)
        self.radius = radius
        self.damage = damage
        self.cx = x          # origin center
        self.cy = y
        self.expansion_speed = getattr(self, "expansion_speed", 8)
        self.max_radius = getattr(self, "max_radius", 120)
        self._affected_ids = set()      # track which enemies already got hit
        self._prev_size = size

    def update(self, dt, game):
        self.life -= dt
        if self.rtype == "blade":
            for e in list(game.room.enemies):
                if distance((self.x, self.y), (e.x, e.y)) <= self.size:
                    game.damage_enemy(e, game.player.atk * 1.5)
        if self.rtype == "blade1":
            for e in list(game.room.enemies):
                if distance((self.x, self.y), (e.x, e.y)) <= self.size:
                    game.damage_enemy(e, game.player.atk * 2.0)
        if self.rtype == "eblade":
            # Check if player is inside the particle radius
            if distance((self.x, self.y), (game.player.x, game.player.y)) <= self.size:
                game.damage_player(self.damage)
        if self.rtype == "eblade1":
            if distance((self.x, self.y), (game.player.x, game.player.y)) <= self.size:
                game.damage_player(self.damage)
        # --- add this inside Particle.update() ---
        elif self.rtype == "frost":
            radius = self.size * 1.2
        elif self.atype == "firetrap":
            # Check each enemy in the room
            for e in list(game.room.enemies):
                if distance((self.x, self.y), (e.x, e.y)) <= self.size + e.size:
                    # Enemy triggered the trap → spawn flame particles
                    for _ in range(50):
                        ang = random.uniform(0, 2 * math.pi)   # random angle
                        r = random.uniform(0, 35)              # random radius
                        px = e.x + math.cos(ang) * r
                        py = e.y + math.sin(ang) * r
                        size = random.uniform(6, 12)

                        flame = Particle(
                            px, py,
                            size,
                            "orange",
                            life=1,
                            owner="player",
                            rtype="flame"
                        )
                        game.particles.append(flame)

                    # Optional: deal damage to the enemy
                    game.damage_enemy(e, 20)  # adjust damage value as needed

                    # Remove the trap after it triggers
                    if self in game.particles:
                        game.particles.remove(self)

                    break   # stop after first enemy triggers
        elif self.atype == "frosttrap":
            # Check each enemy in the room
            for e in list(game.room.enemies):
                if distance((self.x, self.y), (e.x, e.y)) <= self.size + e.size:
                    # Enemy triggered the trap → spawn flame particles
                    for _ in range(15):
                        ang = random.uniform(0, 2 * math.pi)   # random angle
                        r = random.uniform(0, 35)              # random radius
                        px = e.x + math.cos(ang) * r
                        py = e.y + math.sin(ang) * r
                        size = random.randint(4, 8)           # varied snowflake size

                        frost = game.spawn_particle(
                            px, py,
                            size,
                            random.choice(["white", "cyan"]),  # flicker colors
                            life=8,
                            rtype="frost",
                            owner="player"
                        )
                        game.particles.append(frost)


                    # Optional: deal damage to the enemy
                    game.damage_enemy(e, 20)  # adjust damage value as needed

                    # Remove the trap after it triggers
                    if self in game.particles:
                        game.particles.remove(self)

                    break   # stop after first enemy triggers

        elif self.rtype == "flame":
            # simple animation: rise, shrink, flicker color
            self.y -= 0.5
            self.size *= 0.97
            self.color = "orange" if random.random() < 0.55 else "yellow"

            # damage enemies inside the flame radius
            if self.owner == "player":
                # damage enemies
                for e in list(game.room.enemies):
                    if distance((self.x, self.y), (e.x, e.y)) <= self.size:
                        game.damage_enemy(e, self.damage or game.player.mag * 0.5)
            elif self.owner == "enemy":
                # damage player
                if distance((self.x, self.y), (game.player.x, game.player.y)) <= self.size:
                    game.damage_player(self.damage or 5)

        if self.rtype == "shockwave":
            # expand radius
            self._prev_size = self.size
            self.size += self.expansion_speed

            # ring hit: enemy gets affected when the wave reaches them
            for e in list(game.room.enemies):
                eid = id(e)
                if eid in self._affected_ids:
                    continue

                d = distance((self.cx, self.cy), (e.x, e.y))
                # consider enemy size so the ring "touches" them
                if self._prev_size - e.size <= d <= self.size + e.size:
                    # damage
                    if self.damage > 0:
                        game.damage_enemy(e, self.damage)

                    # knockback outward from center
                    ang = math.atan2(e.y - self.cy, e.x - self.cx)
                    # stronger knockback nearer to the origin
                    push = max(6, (self.max_radius - d) * 0.25)
                    e.x += math.cos(ang) * push
                    e.y += math.sin(ang) * push

                    self._affected_ids.add(eid)

            # end when max radius is reached
            if self.size >= self.max_radius:
                return False

        # keep your existing branch/leaf animation etc.
        # keep your existing branch/leaf animation etc.
        if self.rtype in ("branch", "leaf"):
            for e in list(game.room.enemies):
                if distance((self.x, self.y), (e.x, e.y)) <= self.size:
                    game.damage_enemy(e, game.player.wis * 2)
            px, py = game.player.x, game.player.y
            progress = self.age / self.life
            # Extend out, then retract back to player (not past)
            if progress < 0.5:
                reach = self.radius * (progress * 2)
            else:
                # Retract: go from full radius back to 0
                reach = self.radius * (2 - progress * 2)
            
            # Clamp reach to never go negative (past player)
            reach = max(0, reach)
            
            swing = math.sin(progress * math.pi - math.pi/2) * 1
            angle = self.angle + swing
            self.x = px + math.cos(angle) * reach
            self.y = py + math.sin(angle) * reach

        self.age += dt
        return self.life > 0

    def is_dead(self):
        return self.life <= 0

    def draw(self, canvas, background_color="white"):
        if self.rtype == "basic":
            # simple circle particle
            canvas.create_oval(
                self.x - self.size, self.y - self.size,
                self.x + self.size, self.y + self.size,
                fill=self.color, outline=""
            )

        elif self.rtype == "blade":
            # crescent particle
            radius = self.size * 2.0
            offset = self.size * 0.7

            # main circle
            canvas.create_oval(
                self.x - radius, self.y - radius,
                self.x + radius, self.y + radius,
                fill=self.color, outline=self.color
            )

            # cutout circle (to form crescent)
            canvas.create_oval(
                self.x - radius + offset, self.y - radius,
                self.x + radius + offset, self.y + radius,
                fill=background_color, outline=background_color
            )

# ---------- Room ----------
class Room:
    def __init__(self, row, col, dungeon_id=1, player_level=1):
        self.row = row
        self.col = col
        self.enemies = []

        if (row, col) == (0, 0):  # starting room empty
            return

        depth = row + col
        # Spawn enemies scaled to player level
        spawn_enemies_for_dungeon(self, dungeon_id, player_level, count=4 + depth)

        if row == 0 and col == 4:
            spawn_boss_for_room(self, dungeon_id)

# ---------- GameFrame: playable game ----------
class GameFrame(tk.Frame):
    def __init__(self,parent,player,on_quit_to_menu,dungeon_id=1):
        super().__init__(parent)
        self.parent = parent
        self.player = player
        self.on_quit_to_menu = on_quit_to_menu
        self.dungeon_id = dungeon_id 
        self.canvas = tk.Canvas(self,width=WINDOW_W,height=WINDOW_H,bg='black')
        self.canvas.pack()
        self.keys = {}
        self.room_row=0; self.room_col=0
        self.dungeon={}
        self.room=self.get_room(0,0)
        self.projectiles=[]; self.particles=[]
        self.mouse_pos=(WINDOW_W//2,WINDOW_H//2)
        self.show_stats=False
        self.dead=False; self.respawn_time=0; self.respawn_delay=5
        self.bind("o", lambda e: self.open_skill_page())
        self.bind_all('<KeyPress>', self.on_key_down)
        self.bind_all('<KeyRelease>', self.on_key_up)
        self.canvas.bind('<Button-1>', self.handle_stat_click)
        self.player = player
        self.summons = []


        self.last_time=time.time()
        self.after(16,self.loop)
    def open_skill_page(self):
        # Create a new window
        win = tk.Toplevel(self)
        win.title("Skill Management")
        win.geometry("500x600")

        # --- Top: Active skills ---
        ttk.Label(win, text="Active Skills (Keybinds)", font=("Arial", 14, "bold")).pack(pady=10)

        self.active_frame = ttk.Frame(win)
        self.active_frame.pack(pady=5)
        self.refresh_active_skills()

        # --- Bottom: Unlocked skills with assignment buttons ---
        ttk.Label(win, text="Unlocked Skills", font=("Arial", 14, "bold")).pack(pady=10)

        all_frame = ttk.Frame(win)
        all_frame.pack(fill="both", expand=True)

        # Loop through unlocked skills only
        for i, sk in enumerate(self.player.unlocked_skills):
            row = ttk.Frame(all_frame)
            row.grid(row=i//2, column=i%2, padx=5, pady=5, sticky="ew")

            # Skill name centered above the buttons
            name_label = ttk.Label(row, text=sk['name'], anchor="center", font=("Arial", 11, "bold"))
            name_label.pack(fill="x", pady=(0, 3))  # fill across row, small gap below

            # Slot buttons 1–5
            btn_frame = ttk.Frame(row)
            btn_frame.pack()
            for slot in range(1, 6):
                b = ttk.Button(btn_frame, text=str(slot),
                               width=3,
                               command=lambda s=slot, skill=sk: self.assign_skill(skill, s))
                b.pack(side="left", padx=2)

        # Make columns expand evenly
        all_frame.grid_columnconfigure(0, weight=1)
        all_frame.grid_columnconfigure(1, weight=1)


    def refresh_active_skills(self):
        # Clear old widgets
        for w in self.active_frame.winfo_children():
            w.destroy()

        # Show current active skills
        for slot in range(1, 6):
            assigned = next((sk for sk in self.player.unlocked_skills if sk.get('key') == slot), None)
            name = assigned['name'] if assigned else "Empty"
            ttk.Label(self.active_frame, text=f"Slot {slot}: {name}", font=("Arial", 12)).pack(anchor="w")

    def assign_skill(self, skill, slot):
        # Update skill's keybind
        skill['key'] = slot

        # Ensure only one skill per slot
        for sk in self.player.unlocked_skills:
            if sk is not skill and sk['key'] == slot:
                sk['key'] = None

        # Refresh display
        self.refresh_active_skills()
    def get_room(self, row, col):
        key = (row, col)
        if key not in self.dungeon:
            self.dungeon[key] = Room(row, col, self.dungeon_id, player_level=self.player.level)
        return self.dungeon[key]

    def on_key_down(self,e):
        self.keys[e.keysym]=True
        if e.keysym.lower()=='p': self.show_stats = not self.show_stats
        if e.keysym=='Escape': self.on_quit_to_menu()
        if e.keysym.lower()=='o': self.open_skill_page()

    def on_key_up(self,e): self.keys[e.keysym]=False

    def spawn_projectile(self, x, y, angle, speed, life, radius, color, damage, owner="player", ptype='normal', stype="basic"):
        proj = Projectile(x, y, angle, speed, life, radius, color, damage,
                          owner=owner, stype=stype, ptype=ptype)
        self.projectiles.append(proj)
        return proj
    def spawn_particle(self, x, y, size, color,
                       life=1, rtype="basic", owner=None):
        p = Particle(x, y, size, color, life, rtype, owner)
        self.particles.append(p)
        return p



    def damage_player(self,amount):
        if self.dead: return
        amount = max(0, amount - self.player.constitution)
        self.player.hp -= amount
        if self.player.hp <=0:
            self.dead=True
            self.respawn_time=self.respawn_delay
            print("You died! Respawning...")

    def damage_enemy(self,e,amount):
        e.hp -= amount
        if e.hp <=0 and e in self.room.enemies:
            self.player.gain_xp(e.max_hp*2)
            self.room.enemies.remove(e)

    def update_entities(self,dt):
        for e in list(self.room.enemies):
            if isinstance(e, Boss):
                e.update(dt, self)
            else:
                e.update(self)  # <--- CHANGE TO: e.update(self)
        for p in list(self.projectiles): p.update(dt,self)
        self.projectiles=[p for p in self.projectiles if p.life>0]
        for part in self.particles: part.update(dt, self)
        self.particles=[p for p in self.particles if p.life>0]
        self.player.unlock_skills()
        for s in list(self.summons):
            s.update(self, dt)
        # --- Summon vs summon ---
        for i, s1 in enumerate(self.summons):
            for j, s2 in enumerate(self.summons):
                if i < j:
                    resolve_overlap(s1, s2)

        # --- Summon vs player ---
        for s in self.summons:
            resolve_overlap(s, self.player)

        # --- Summon vs enemy ---
        for s in self.summons:
            for e in self.room.enemies:
                resolve_overlap(s, e)


    def update_player(self,dt):
        p=self.player
        p.hp=min(p.max_hp, p.hp+p.hp_regen*dt)
        p.mana=min(p.max_mana, p.mana+p.mana_regen*dt)

        if self.dead:
            self.respawn_time -= dt
            if self.respawn_time<=0:
                p.x = WINDOW_W//2; p.y = WINDOW_H//2
                self.particles.clear()
                self.projectiles.clear()
                p.hp = p.max_hp; p.mana = p.max_mana
                self.dead=False
                self.room_row=0; self.room_col=0; self.room=self.get_room(0,0)
                print("Respawned!")
            return

        # movement
        if self.keys.get('Up'):
            p.y -= p.speed
        if self.keys.get('Down'):
            p.y += p.speed
        if self.keys.get('Left'):
            p.x -= p.speed
        if self.keys.get('Right'):
            p.x += p.speed

        # room transitions
        # compute current room before checking transitions
        current_row = self.room_row
        current_col = self.room_col

        if p.x < 0:
            self.room_col = max(0, self.room_col - 1)
            p.x = WINDOW_W - 10
            self.room = self.get_room(self.room_row, self.room_col)
            self.particles.clear()
            self.projectiles.clear()
            for s in self.summons:
                s.room_row = self.room_row
                s.room_col = self.room_col
                s.x = self.player.x + 20
                s.y = self.player.y + 20

        if p.x > WINDOW_W:
            self.room_col = min(ROOM_COLS - 1, self.room_col + 1)
            p.x = 10
            self.room = self.get_room(self.room_row, self.room_col)
            self.particles.clear()
            self.projectiles.clear()
            for s in self.summons:
                s.room_row = self.room_row
                s.room_col = self.room_col
                s.x = self.player.x + 20
                s.y = self.player.y + 20

        if p.y < 0:
            self.room_row = max(0, self.room_row - 1)
            p.y = WINDOW_H - 10
            self.room = self.get_room(self.room_row, self.room_col)
            self.particles.clear()
            self.projectiles.clear()
            for s in self.summons:
                s.room_row = self.room_row
                s.room_col = self.room_col
                s.x = self.player.x + 20
                s.y = self.player.y + 20

        if p.y > WINDOW_H:
            self.room_row = min(ROOM_ROWS - 1, self.room_row + 1)
            p.y = 10
            self.room = self.get_room(self.room_row, self.room_col)
            self.particles.clear()
            self.projectiles.clear()
            for s in self.summons:
                s.room_row = self.room_row
                s.room_col = self.room_col
                s.x = self.player.x + 20
                s.y = self.player.y + 20

        p.x = clamp(p.x, 0, WINDOW_W)
        p.y = clamp(p.y, 0, WINDOW_H)

        # skills usage
        now=time.time()
        for sk in p.unlocked_skills:
            key=str(sk['key'])
            if self.keys.get(key) or self.keys.get('KP_'+key):
                base_cd = sk.get('cooldown',0); mod=sk.get('cooldown_mod',1.0)
                last_used=sk.get('last_used',0)
                effective_cd = base_cd*mod
                if effective_cd<=0:
                    sk['skill'](p,self); sk['last_used']=now
                elif now-last_used>=effective_cd:
                    sk['skill'](p,self); sk['last_used']=now
                    sk['cooldown_mod']=max(0.2, mod*0.995)

    def handle_stat_click(self,event):
        if not self.show_stats or self.player.stat_points<=0: return
        mx,my=event.x,event.y
        stat_y_start=120; stat_height=30
        stats=['strength','vitality','agility','constitution','intelligence','wisdom','will']
        for i,stat in enumerate(stats):
            btn_x=600; btn_y=stat_y_start+i*stat_height
            btn_w,btn_h=30,20
            if btn_x<mx<btn_x+btn_w and btn_y<my<btn_y+btn_h:
                setattr(self.player,stat,getattr(self.player,stat)+1)
                self.player.stat_points -= 1
                self.player.update_stats()

    def draw(self):
        self.canvas.delete('all')
        px, py = self.player.x, self.player.y
        size = 12
        self.canvas.create_oval(px-size-2, py-size-2, px+size+2, py+size+2, fill='white')  # outline
        self.canvas.create_oval(px-size, py-size, px+size, py+size, fill='cyan')           # player body
        for s in self.summons:
            s.draw(self.canvas)

        for e in self.room.enemies:
            ex, ey = e.x, e.y
            if isinstance(e, Boss):
                boss_shapes = {
                    "FireLord": ("rectangle", "orange"),
                    "IceGiant": ("diamond", "cyan"),
                    "ShadowWraith": ("triangle", "purple"),
                    "EarthTitan": ("oval", "brown"),
                }
                outline_width = 3  # thickness of outline
                outline_color = "white"
                shape, color = boss_shapes.get(e.boss_type, ("oval", "orange"))

                size = e.size

                if shape == "oval":
                    self.canvas.create_oval(
                        ex-size, ey-size, ex+size, ey+size,
                        fill=color, outline=outline_color, width=outline_width
                    )

                elif shape == "rectangle":
                    self.canvas.create_rectangle(
                        ex-size, ey-size, ex+size, ey+size,
                        fill=color, outline=outline_color, width=outline_width
                    )

                elif shape == "triangle":
                    points = [ex, ey-size, ex+size, ey+size, ex-size, ey+size]
                    self.canvas.create_polygon(
                        points, fill=color, outline=outline_color, width=outline_width
                    )

                elif shape == "diamond":
                    points = [ex, ey-size, ex+size, ey, ex, ey+size, ex-size, ey]
                    self.canvas.create_polygon(
                        points, fill=color, outline=outline_color, width=outline_width
                    )

                continue


            enemy_shapes = {
                "Swordman": ("oval", "brown"),
                "Spearman": ("hexagon", "brown"),
                "Archer": ("rectangle", "brown"),
                "Fire Imp": ("triangle", "orange"),
                "Flame Elemental": ("diamond", "red"),
                "Troll": ("rectangle", "darkgray"),
                "Ice Golem": ("square", "cyan"),
                "Dark Mage": ("triangle", "purple"),
                "Summoner": ("oval", "pink"),
                "Venom Lurker": ("oval", "lime"),
                "Healer": ("triangle", "yellow"),
            }

            shape, color = enemy_shapes.get(e.name, ("oval", "gray"))

            if shape == "oval":
                self.canvas.create_oval(ex-e.size, ey-e.size, ex+e.size, ey+e.size, fill=color)
            elif shape == "rectangle":
                self.canvas.create_rectangle(ex-e.size, ey-e.size, ex+e.size, ey+e.size, fill=color)
            elif shape == "triangle":
                points = [ex, ey-e.size, ex+e.size, ey+e.size, ex-e.size, ey+e.size]
                self.canvas.create_polygon(points, fill=color)
            elif shape == "square":
                self.canvas.create_rectangle(ex-e.size, ey-e.size, ex+e.size, ey+e.size, fill=color)
            elif shape == "diamond":
                points = [ex, ey-e.size, ex+e.size, ey, ex, ey+e.size, ex-e.size, ey]
                self.canvas.create_polygon(points, fill=color)
            elif shape == "hexagon":
                points = [
                    ex, ey-e.size,
                    ex+e.size*0.87, ey-e.size*0.5,
                    ex+e.size*0.87, ey+e.size*0.5,
                    ex, ey+e.size,
                    ex-e.size*0.87, ey+e.size*0.5,
                    ex-e.size*0.87, ey-e.size*0.5
                ]
                self.canvas.create_polygon(points, fill=color)

            # Draw health above the enemy
            health_text = f"{e.hp}/{e.max_hp}"
            self.canvas.create_text(ex, ey - e.size - 10, text=health_text, fill='white')
            
        boss_in_room = None
        for e in self.room.enemies:
            if isinstance(e, Boss):
                boss_in_room = e
                break

        if boss_in_room:
            # Draw boss health bar at top
            bar_width = 400
            bar_height = 20
            x0 = (WINDOW_W - bar_width)//2
            y0 = 20
            hp_frac = boss_in_room.hp / boss_in_room.max_hp if boss_in_room.max_hp else 0
            self.canvas.create_rectangle(x0, y0, x0+bar_width, y0+bar_height, fill='gray')
            self.canvas.create_rectangle(x0, y0, x0 + int(bar_width*hp_frac), y0+bar_height, fill='red')
            self.canvas.create_text(WINDOW_W//2, y0 + bar_height//2, text=f"{boss_in_room.name}", fill='white', font=('Arial','12','bold'))
            health_text = f"{boss_in_room.hp}/{boss_in_room.max_hp}"
            self.canvas.create_text(ex, ey - e.size - 5, text=health_text, fill='white')

        

        for proj in self.projectiles:
            x, y, r = proj.x, proj.y, proj.radius
            if proj.stype == 'basic':
                # Simple circle
                self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=proj.color)
            if proj.stype == 'arrow':
                angle = proj.angle
                x, y = proj.x, proj.y
                r = proj.radius  # base radius
                scale = 0.4  # shrink factor

                # ----- Arrow tip (triangle) -----
                tip_length = r * 4 * scale
                tip = [
                    x + math.cos(angle) * tip_length, y + math.sin(angle) * tip_length,  # tip point
                    x - math.cos(angle + math.pi/6) * tip_length/2, y - math.sin(angle + math.pi/6) * tip_length/2,  # left base
                    x - math.cos(angle - math.pi/6) * tip_length/2, y - math.sin(angle - math.pi/6) * tip_length/2   # right base
                ]
                self.canvas.create_polygon(tip, fill='gray')  # tip gray

                # ----- Arrow shaft (rectangle) -----
                shaft_length = tip_length * 1.5
                shaft_width = r / 2 * scale
                perp_angle = angle + math.pi / 2
                corners = [
                    x - math.cos(perp_angle) * shaft_width - math.cos(angle) * shaft_length, y - math.sin(perp_angle) * shaft_width - math.sin(angle) * shaft_length - 1,
                    x + math.cos(perp_angle) * shaft_width - math.cos(angle) * shaft_length, y + math.sin(perp_angle) * shaft_width - math.sin(angle) * shaft_length + 1,
                    x + math.cos(perp_angle) * shaft_width, y + math.sin(perp_angle) * shaft_width,
                    x - math.cos(perp_angle) * shaft_width, y - math.sin(perp_angle) * shaft_width
                ]
                self.canvas.create_polygon(corners, fill=proj.color)

                # ----- Fletching at the back -----
                fletch_length = r * 3 * scale
                fletch_width = r * scale
                back_x = x - math.cos(angle) * shaft_length
                back_y = y - math.sin(angle) * shaft_length

                fletch_angles = [-math.pi/8, 0, math.pi/8]
                for fa in fletch_angles:
                    ftip_x = back_x - math.cos(angle + fa) * fletch_length
                    ftip_y = back_y - math.sin(angle + fa) * fletch_length
                    base1_x = back_x - math.cos(angle + fa + math.pi/2) * fletch_width/2
                    base1_y = back_y - math.sin(angle + fa + math.pi/2) * fletch_width/2
                    base2_x = back_x + math.cos(angle + fa + math.pi/2) * fletch_width/2
                    base2_y = back_y + math.sin(angle + fa + math.pi/2) * fletch_width/2
                    self.canvas.create_polygon([ftip_x, ftip_y, base1_x, base1_y, base2_x, base2_y], fill='white')
            elif proj.stype == "lightning":
                strands = 1        # number of lightning strands
                segments = 50      # length of each strand
                for s in range(strands):
                    points = []
                    dx = math.cos(proj.angle) * (proj.radius * 12 / segments)
                    dy = math.sin(proj.angle) * (proj.radius * 12 / segments)
                    px, py = proj.x, proj.y
                    for i in range(segments):
                        offset_x = random.uniform(-8, 8)
                        offset_y = random.uniform(-8, 8)
                        points.append((px + dx * i + offset_x, py + dy * i + offset_y))
                    # flicker: sometimes skip drawing this strand
                    if random.random() < 0.85:   # 80% chance to draw
                        for i in range(len(points) - 1):
                            x1, y1 = points[i]
                            x2, y2 = points[i + 1]
                            self.canvas.create_line(x1, y1, x2, y2,
                                                    fill="yellow", width=4)
            elif proj.stype == "howl":
                arc_extent = 90   # cone width
                thickness = 6

                # Tkinter arc angles: 0° = right, CCW positive
                start_angle = -math.degrees(proj.angle)

                for i in range(3):
                    radius = proj.radius * (i + 2)
                    self.canvas.create_arc(
                        proj.x - radius, proj.y - radius,
                        proj.x + radius, proj.y + radius,
                        start=start_angle - arc_extent / 2,
                        extent=arc_extent,
                        style="arc",
                        outline=proj.color,
                        width=thickness
                    )



            elif proj.stype == 'dagger':
                # Arrow = triangle + rectangle + triangle along angle
                length = r*4
                width = r
                # Tip triangle
                tip = [
                    x + math.cos(proj.angle)*length/2, y + math.sin(proj.angle)*length/2,
                    x + math.cos(proj.angle + 2.5)*width, y + math.sin(proj.angle + 2.5)*width,
                    x + math.cos(proj.angle - 2.5)*width, y + math.sin(proj.angle - 2.5)*width
                ]
                self.canvas.create_polygon(tip, fill=proj.color)
                # Shaft rectangle
                x1 = x - math.cos(proj.angle)*length/2
                y1 = y - math.sin(proj.angle)*length/2
                self.canvas.create_rectangle(x1-width/2, y1-width/2, x1+width/2, y1+width/2, fill=proj.color)
            elif proj.stype == 'bolt':
                # Smaller rectangle
                length = r * 4        # reduced length
                width = r * 1.0       # reduced width

                # Center line endpoints
                x1 = x - math.cos(proj.angle) * length / 2
                y1 = y - math.sin(proj.angle) * length / 2
                x2 = x + math.cos(proj.angle) * length / 2
                y2 = y + math.sin(proj.angle) * length / 2

                # Perpendicular offset for width
                dx = math.sin(proj.angle) * width / 2
                dy = -math.cos(proj.angle) * width / 2

                # Rectangle points
                points = [
                    x1 - dx, y1 - dy,
                    x1 + dx, y1 + dy,
                    x2 + dx, y2 + dy,
                    x2 - dx, y2 - dy
                ]
                self.canvas.create_polygon(points, fill=proj.color)

                # Semicircle at the front (same width as rectangle)
                radius = width / 2     # diameter = rectangle width
                bbox = [
                    x2 - radius, y2 - radius,
                    x2 + radius, y2 + radius
                ]
                start_angle = math.degrees(proj.angle) - 90
                self.canvas.create_arc(bbox, start=start_angle, extent=180,
                                       fill=proj.color, outline=proj.color)
            elif proj.stype == 'slash':
                # --- CLEAN TAPERED CRESCENT BLADE ---
                r = proj.radius * 1.5
                max_thickness = proj.radius * 0.45   # thick in the middle
                angle = proj.angle
                cx, cy = proj.x, proj.y

                # Rotation helper
                def rot(x, y):
                    return (
                        cx + x * math.cos(angle) - y * math.sin(angle),
                        cy + x * math.sin(angle) + y * math.cos(angle)
                    )

                outer = []
                inner = []

                # Build outer arc and thin inner arc
                for a in range(-70, 71, 10):
                    rad = math.radians(a)

                    # Outer arc point
                    ox = math.cos(rad) * r
                    oy = math.sin(rad) * r
                    outer.append(rot(ox, oy))

                    # Taper thickness from center → ends
                    taper_factor = 1 - abs(a) / 70   # 1 at center, 0 at tips
                    thickness = max_thickness * taper_factor

                    # Inner arc point (closer to the outer arc near the tips)
                    ix = math.cos(rad) * (r - thickness)
                    iy = math.sin(rad) * (r - thickness)
                    inner.append(rot(ix, iy))

                # Combine into a single crescent polygon
                blade_points = []
                for x, y in outer + inner[::-1]:
                    blade_points += [x, y]

                self.canvas.create_polygon(
                    blade_points,
                    fill=proj.color,
                    outline=proj.color,
                    width=1
                )
            elif proj.stype == 'slash2':
                # --- CLEAN TAPERED CRESCENT BLADE ---
                r = proj.radius * 2
                max_thickness = proj.radius * 3   # thick in the middle
                angle = proj.angle
                cx, cy = proj.x, proj.y

                # Rotation helper
                def rot(x, y):
                    return (
                        cx + x * math.cos(angle) - y * math.sin(angle),
                        cy + x * math.sin(angle) + y * math.cos(angle)
                    )

                outer = []
                inner = []

                # Build outer arc and thin inner arc
                for a in range(-70, 71, 10):
                    rad = math.radians(a)

                    # Outer arc point
                    ox = math.cos(rad) * r
                    oy = math.sin(rad) * r
                    outer.append(rot(ox, oy))

                    # Taper thickness from center → ends
                    taper_factor = 1 - abs(a) / 70   # 1 at center, 0 at tips
                    thickness = max_thickness * taper_factor

                    # Inner arc point (closer to the outer arc near the tips)
                    ix = math.cos(rad) * (r - thickness)
                    iy = math.sin(rad) * (r - thickness)
                    inner.append(rot(ix, iy))

                # Combine into a single crescent polygon
                blade_points = []
                for x, y in outer + inner[::-1]:
                    blade_points += [x, y]

                self.canvas.create_polygon(
                    blade_points,
                    fill=proj.color,
                    outline=proj.color,
                    width=1
                )

            elif proj.stype == 'bolt1':
                # Even smaller rectangle
                length = r * 2.5      # shorter body
                width = r * 0.6       # narrower body

                # Center line endpoints
                x1 = x - math.cos(proj.angle) * length / 2
                y1 = y - math.sin(proj.angle) * length / 2
                x2 = x + math.cos(proj.angle) * length / 2
                y2 = y + math.sin(proj.angle) * length / 2

                # Perpendicular offset for width
                dx = math.sin(proj.angle) * width / 2
                dy = -math.cos(proj.angle) * width / 2

                # Rectangle points
                points = [
                    x1 - dx, y1 - dy,
                    x1 + dx, y1 + dy,
                    x2 + dx, y2 + dy,
                    x2 - dx, y2 - dy
                ]
                self.canvas.create_polygon(points, fill=proj.color)

                # Rounded nose at the front (same width as rectangle)
                radius = width / 2     # diameter = rectangle width
                bbox = [
                    x2 - radius, y2 - radius,
                    x2 + radius, y2 + radius
                ]
                start_angle = math.degrees(proj.angle) - 90
                self.canvas.create_arc(bbox, start=start_angle, extent=180,
                                       fill=proj.color, outline=proj.color)


        for part in self.particles:
            if part.rtype == "basic":
                self.canvas.create_oval(
                    part.x - part.size, part.y - part.size,
                    part.x + part.size, part.y + part.size,
                    fill=part.color
                )
            elif part.rtype == "trap":
                size = part.size
                ang = getattr(part, "angle", 0)

                # Equilateral triangle: 3 points spaced 120° apart
                p1 = (part.x + math.cos(ang) * size,
                      part.y + math.sin(ang) * size)
                p2 = (part.x + math.cos(ang + 2*math.pi/3) * size,
                      part.y + math.sin(ang + 2*math.pi/3) * size)
                p3 = (part.x + math.cos(ang + 4*math.pi/3) * size,
                      part.y + math.sin(ang + 4*math.pi/3) * size)

                self.canvas.create_polygon(p1, p2, p3,
                                      fill=part.color,
                                      outline="white",
                                      width=2)
            elif part.rtype == "diamond":
                # Simple, static diamond centered at the particle's position.
                s = part.size
                cx, cy = part.x, part.y

                points = [
                    cx,     cy - s,  # top
                    cx + s, cy,      # right
                    cx,     cy + s,  # bottom
                    cx - s, cy       # left
                ]
                self.canvas.create_polygon(points, fill="yellow", outline="gold", width=2)
            # --- inside GameFrame.draw(), in the loop: for part in self.particles ---
            elif part.rtype == "flame":
                r = part.size
                tip_x = part.x
                tip_y = part.y - r * 1.5

                # body (teardrop polygon)
                self.canvas.create_polygon(
                    part.x - r, part.y,      # left base
                    part.x + r, part.y,      # right base
                    tip_x, tip_y,            # tip
                    fill=part.color, outline=""
                )

                # inner glow
                self.canvas.create_oval(
                    part.x - r * 0.6, part.y - r * 0.6,
                    part.x + r * 0.6, part.y + r * 0.6,
                    fill="yellow", outline=""
                )
            elif part.rtype == "frost":
                # size and center
                s = part.size
                cx, cy = part.x, part.y

                # flicker color each frame
                color = "white" if random.random() < 0.5 else "cyan"

                # per-frame rotation (visual only)
                ang = (time.time() * 2.0) % (2 * math.pi)

                def rot(px, py):
                    rx = cx + px * math.cos(ang) - py * math.sin(ang)
                    ry = cy + px * math.sin(ang) + py * math.cos(ang)
                    return rx, ry

                # arms: cross + diagonals (snowflake star)
                arms = [
                    ((-s, 0), (s, 0)),          # horizontal
                    ((0, -s), (0, s)),          # vertical
                    ((-0.75*s, -0.75*s), (0.75*s, 0.75*s)),   # diag 1
                    ((0.75*s, -0.75*s), (-0.75*s, 0.75*s)),   # diag 2
                ]

                # draw arms
                for (ax1, ay1), (ax2, ay2) in arms:
                    x1, y1 = rot(ax1, ay1)
                    x2, y2 = rot(ax2, ay2)
                    self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2)

                # subtle inner glow like flame’s oval, but cyan/white
                glow_r = s * 0.5
                self.canvas.create_oval(
                    cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r,
                    fill="light cyan" if color == "cyan" else "white", outline=""
                )


            elif part.rtype == "blade":
                # --- CLEAN TAPERED CRESCENT BLADE ---
                r = part.size * 1.5
                max_thickness = part.size * 0.45   # thick in the middle
                angle = part.angle
                cx, cy = part.x, part.y

                # Rotation helper
                def rot(x, y):
                    return (
                        cx + x * math.cos(angle) - y * math.sin(angle),
                        cy + x * math.sin(angle) + y * math.cos(angle)
                    )

                outer = []
                inner = []

                # Build outer arc and thin inner arc
                for a in range(-70, 71, 10):
                    rad = math.radians(a)

                    # Outer arc point
                    ox = math.cos(rad) * r
                    oy = math.sin(rad) * r
                    outer.append(rot(ox, oy))

                    # Taper thickness from center → ends
                    taper_factor = 1 - abs(a) / 70   # 1 at center, 0 at tips
                    thickness = max_thickness * taper_factor

                    # Inner arc point (closer to the outer arc near the tips)
                    ix = math.cos(rad) * (r - thickness)
                    iy = math.sin(rad) * (r - thickness)
                    inner.append(rot(ix, iy))

                # Combine into a single crescent polygon
                blade_points = []
                for x, y in outer + inner[::-1]:
                    blade_points += [x, y]

                self.canvas.create_polygon(
                    blade_points,
                    fill=part.color,
                    outline=part.color,
                    width=1
                )
            elif part.rtype == "eblade":
                # --- CLEAN TAPERED CRESCENT BLADE ---
                r = part.size * 1.5
                max_thickness = part.size * 0.45   # thick in the middle
                angle = part.angle
                cx, cy = part.x, part.y

                # Rotation helper
                def rot(x, y):
                    return (
                        cx + x * math.cos(angle) - y * math.sin(angle),
                        cy + x * math.sin(angle) + y * math.cos(angle)
                    )

                outer = []
                inner = []

                # Build outer arc and thin inner arc
                for a in range(-70, 71, 10):
                    rad = math.radians(a)

                    # Outer arc point
                    ox = math.cos(rad) * r
                    oy = math.sin(rad) * r
                    outer.append(rot(ox, oy))

                    # Taper thickness from center → ends
                    taper_factor = 1 - abs(a) / 70   # 1 at center, 0 at tips
                    thickness = max_thickness * taper_factor

                    # Inner arc point (closer to the outer arc near the tips)
                    ix = math.cos(rad) * (r - thickness)
                    iy = math.sin(rad) * (r - thickness)
                    inner.append(rot(ix, iy))

                # Combine into a single crescent polygon
                blade_points = []
                for x, y in outer + inner[::-1]:
                    blade_points += [x, y]

                self.canvas.create_polygon(
                    blade_points,
                    fill=part.color,
                    outline=part.color,
                    width=1
                )
            elif part.rtype == "blade1":
                # --- CLEAN TAPERED CRESCENT BLADE ---
                r = part.size * 0.4
                max_thickness = part.size * 0.4   # thick in the middle
                angle = part.angle
                cx, cy = part.x, part.y

                # Rotation helper
                def rot(x, y):
                    return (
                        cx + x * math.cos(angle) - y * math.sin(angle),
                        cy + x * math.sin(angle) + y * math.cos(angle)
                    )

                outer = []
                inner = []

                # Build outer arc and thin inner arc
                for a in range(-70, 71, 10):
                    rad = math.radians(a)

                    # Outer arc point
                    ox = math.cos(rad) * r
                    oy = math.sin(rad) * r
                    outer.append(rot(ox, oy))

                    # Taper thickness from center → ends
                    taper_factor = 1 - abs(a) / 70   # 1 at center, 0 at tips
                    thickness = max_thickness * taper_factor

                    # Inner arc point (closer to the outer arc near the tips)
                    ix = math.cos(rad) * (r - thickness)
                    iy = math.sin(rad) * (r - thickness)
                    inner.append(rot(ix, iy))

                # Combine into a single crescent polygon
                blade_points = []
                for x, y in outer + inner[::-1]:
                    blade_points += [x, y]

                self.canvas.create_polygon(
                    blade_points,
                    fill=part.color,
                    outline=part.color,
                    width=1
        )
            elif part.rtype == "eblade1":
                # --- CLEAN TAPERED CRESCENT BLADE ---
                r = part.size * 0.4
                max_thickness = part.size * 0.4   # thick in the middle
                angle = part.angle
                cx, cy = part.x, part.y

                # Rotation helper
                def rot(x, y):
                    return (
                        cx + x * math.cos(angle) - y * math.sin(angle),
                        cy + x * math.sin(angle) + y * math.cos(angle)
                    )

                outer = []
                inner = []

                # Build outer arc and thin inner arc
                for a in range(-70, 71, 10):
                    rad = math.radians(a)

                    # Outer arc point
                    ox = math.cos(rad) * r
                    oy = math.sin(rad) * r
                    outer.append(rot(ox, oy))

                    # Taper thickness from center → ends
                    taper_factor = 1 - abs(a) / 70   # 1 at center, 0 at tips
                    thickness = max_thickness * taper_factor

                    # Inner arc point (closer to the outer arc near the tips)
                    ix = math.cos(rad) * (r - thickness)
                    iy = math.sin(rad) * (r - thickness)
                    inner.append(rot(ix, iy))

                # Combine into a single crescent polygon
                blade_points = []
                for x, y in outer + inner[::-1]:
                    blade_points += [x, y]

                self.canvas.create_polygon(
                    blade_points,
                    fill=part.color,
                    outline=part.color,
                    width=1
        )
            elif part.rtype == "shield":
                # outlined circle (no fill)
                self.canvas.create_oval(
                    part.x - part.size, part.y - part.size,
                    part.x + part.size, part.y + part.size,
                    outline=part.color, width=2
                )
            elif part.rtype == "branch":
                # Draw the whip line from player to animated position
                self.canvas.create_line(
                    self.player.x, self.player.y,
                    part.x, part.y,
                    fill=part.color, width=5, smooth=True
                )
                # Draw tip circle
                self.canvas.create_oval(
                    part.x - part.size, part.y - part.size,
                    part.x + part.size, part.y + part.size,
                    fill=part.color, outline=""
                )
            elif part.rtype == "leaf":
                # Draw small leaf at animated position
                self.canvas.create_oval(
                    part.x - part.size, part.y - part.size,
                    part.x + part.size, part.y + part.size,
                    fill=part.color, outline=""
                )
            elif part.rtype == "shockwave":
                # Draw a layered expanding ring centered on the particle
                self.canvas.create_oval(
                    part.x - part.size, part.y - part.size,
                    part.x + part.size, part.y + part.size,
                    outline="white", width=6
                )
                self.canvas.create_oval(
                    part.x - part.size, part.y - part.size,
                    part.x + part.size, part.y + part.size,
                    outline="yellow", width=3
                )



        # HUD: HP/Mana/XP
        self.canvas.create_rectangle(10,10,210,30,fill='gray')
        hpw=int((self.player.hp/self.player.max_hp)*200) if self.player.max_hp else 0
        self.canvas.create_rectangle(10,10,10+hpw,30,fill='red')

        self.canvas.create_rectangle(10,35,210,55,fill='gray')
        mw=int((self.player.mana/self.player.max_mana)*200) if self.player.max_mana else 0
        self.canvas.create_rectangle(10,35,10+mw,55,fill='blue')

        self.canvas.create_rectangle(10,60,210,70,fill='gray')
        xpw=int((self.player.xp/self.player.xp_to_next)*200) if self.player.xp_to_next else 0
        self.canvas.create_rectangle(10,60,10+xpw,70,fill='green')
        self.canvas.create_text(220,60,text=f'LV {self.player.level}',fill='white',anchor='nw')

        # Skills icons + cooldown overlay
        now=time.time()
        for i,sk in enumerate(self.player.unlocked_skills[:5]):
            x0=10+i*60; y0=80; size=50
            self.canvas.create_rectangle(x0,y0,x0+size,y0+size,fill='blue')
            base_cd=sk.get('cooldown',0); mod=sk.get('cooldown_mod',1.0); last_used=sk.get('last_used',0)
            effective_cd=base_cd*mod
            cd_remaining=max(0,effective_cd-(now-last_used))
            if effective_cd>0 and cd_remaining>0:
                frac=clamp(cd_remaining/effective_cd,0.0,1.0)
                overlay_h=int(size*frac)
                self.canvas.create_rectangle(x0,y0,x0+size,y0+overlay_h,fill='grey')
            self.canvas.create_text(x0+size/2,y0+size/2,text=sk['name'][0],fill='white')

        if self.show_stats: self.draw_stats_panel()
        self.canvas.create_text(650,10,text=f'Room: ({self.room_row},{self.room_col})',fill='white')

    def draw_stats_panel(self):
        p=self.player
        self.canvas.create_rectangle(100,100,700,500,fill='#222')
        stats=['strength','vitality','agility','constitution','intelligence','wisdom','will',]
        y_start=120; stat_height=30
        for i,stat in enumerate(stats):
            val=getattr(p,stat)
            self.canvas.create_text(120,y_start+i*stat_height,anchor='nw',text=f'{stat.upper()}: {val}',fill='white',font=('Arial','14'))
            if p.stat_points>0:
                self.canvas.create_rectangle(600,y_start+i*stat_height,630,y_start+i*stat_height+20,fill='green')
                self.canvas.create_text(615,y_start+i*stat_height+10,text='+',fill='white')
        self.canvas.create_text(120,350,text=f'                                              Stat Points Available: {p.stat_points}',fill='yellow',font=('Arial','14'))

    def loop(self):
        now=time.time(); dt=now-self.last_time; self.last_time=now
        self.update_player(dt)
        self.update_entities(dt)
        self.draw()
        self.after(16,self.loop)
        for enemy in self.room.enemies:
            resolve_overlap(self.player, enemy)

        # Enemy vs enemy
        for i, e1 in enumerate(self.room.enemies):
            for j, e2 in enumerate(self.room.enemies):
                if i < j:  # avoid double-checking
                    resolve_overlap(e1, e2)
# ---------- Main window with Home Screen ----------
class MainApp(tk.Tk):
    SAVE_FILE = "player_save.json"
    
    CLASS_INFO = {
        'Warrior': {'emoji': '⚔️', 'color': '#d32f2f', 'desc': 'Master of melee combat\nHigh HP and physical damage'},
        'Mage': {'emoji': '🔮', 'color': '#1976d2', 'desc': 'Wields elemental magic\nPowerful spells and mana'},
        'Rogue': {'emoji': '🗡️', 'color': '#7b1fa2', 'desc': 'Swift and deadly striker\nHigh agility and burst damage'},
        'Cleric': {'emoji': '✨', 'color': '#fbc02d', 'desc': 'Holy warrior and healer\nSupport and light magic'},
        'Druid': {'emoji': '🍃', 'color': '#388e3c', 'desc': 'Nature\'s guardian\nSummons and natural magic'},
        'Monk': {'emoji': '👊', 'color': '#ff6f00', 'desc': 'Chi-powered fighter\nUses HP for devastating attacks'},
        'Ranger': {'emoji': '🏹', 'color': '#5d4037', 'desc': 'Expert archer and trapper\nRanged attacks and tactical skills'}
    }

    def reset_character(self):
        if not hasattr(self, 'preview_player'):
            return
        from tkinter import messagebox
        if messagebox.askyesno("Reset Character", "Are you sure you want to reset your character?"):
            self.preview_player.reset()
            self.class_chosen = False
            self.update_preview()
            self.build_home()
            self.save_player(self.preview_player.to_dict())

    def __init__(self):
        super().__init__()
        self.title("Dungeon LitRPG - Hub")
        self.geometry("1000x850")
        self.resizable(False, False)
        self.configure(bg='#0a0a0a')

        self.class_chosen = False

        self.player_data = self.load_player() or {"name": "Hero", "class_name": ""}
        self.selected_class = self.player_data.get("class_name", "")
        if self.selected_class:
            self.class_chosen = True

        self.name_var = tk.StringVar(value=self.player_data.get("name", "Hero"))
        self.preview_player = Player(self.name_var.get(), self.selected_class or "Warrior")
        self.preview_player.unlock_skills()

        self.home_frame = tk.Frame(self, bg='#1a1a1a')
        self.home_frame.pack(fill='both', expand=True)
        self.game_frame_container = None

        self.build_home()

    def build_home(self):
        for w in self.home_frame.winfo_children(): w.destroy()
        
        # Header section - grayscale only
        header = tk.Frame(self.home_frame, bg='#1a1a1a', height=80)
        header.pack(fill='x', pady=(0, 20))
        header.pack_propagate(False)
        
        title = tk.Label(header, text="⚔️ DUNGEON HUB ⚔️", font=("Arial", 32, "bold"), 
                        bg='#1a1a1a', fg='#ffffff')
        title.pack(pady=20)

        # Character info section - grayscale
        info_frame = tk.Frame(self.home_frame, bg='#2a2a2a', bd=2, relief='groove')
        info_frame.pack(pady=10, padx=50, fill='x')
        
        name_frame = tk.Frame(info_frame, bg='#2a2a2a')
        name_frame.pack(pady=15)
        
        tk.Label(name_frame, text="Hero Name:", font=("Arial", 14, "bold"), 
                bg='#2a2a2a', fg='#e0e0e0').pack(side='left', padx=(20, 10))
        name_entry = tk.Entry(name_frame, textvariable=self.name_var, font=("Arial", 14),
                             bg='#3a3a3a', fg='white', insertbackground='white', width=25, bd=2)
        name_entry.pack(side='left', padx=10)

        # Class selection area
        if not self.class_chosen:
            class_label = tk.Label(self.home_frame, text="Choose Your Class", 
                                  font=("Arial", 20, "bold"), bg='#0a0a0a', fg='#ffffff')
            class_label.pack(pady=(20, 10))
            # Class buttons container
            classes_container = tk.Frame(self.home_frame, bg='#1a1a1a')
            classes_container.pack(pady=10)
            
            # Row 1: Warrior, Mage, Rogue, Cleric
            row1 = tk.Frame(classes_container, bg='#1a1a1a')
            row1.pack(pady=5)
            for cls in ['Warrior', 'Mage', 'Rogue', 'Cleric']:
                self.create_class_button(row1, cls)
            
            # Row 2: Druid, Monk, Ranger
            row2 = tk.Frame(classes_container, bg='#1a1a1a')
            row2.pack(pady=5)
            for cls in ['Druid', 'Monk', 'Ranger']:
                self.create_class_button(row2, cls)

        # Reset button
        reset_btn = tk.Button(self.home_frame, text="🔄 Reset Character", font=("Arial", 12, "bold"),
                             bg='#4a4a4a', fg='white', activebackground='#6a6a6a', 
                             command=self.reset_character, bd=0, padx=20, pady=8,
                             cursor='hand2')
        reset_btn.pack(pady=10)

        # Preview panel
        preview_frame = tk.Frame(self.home_frame, bg='#2d2d2d', bd=3, relief='ridge')
        preview_frame.pack(pady=15, fill='x', padx=40)
        
        preview_title = tk.Label(preview_frame, text="📊 Character Preview", 
                                font=("Arial", 16, "bold"), bg='#2d2d2d', fg='#ffd700')
        preview_title.pack(pady=10)
        
        self.preview_text = tk.Text(preview_frame, height=7, width=80, bg='#1a1a1a', 
                                   fg='#00ff00', font=("Courier", 11), bd=0)
        self.preview_text.pack(padx=15, pady=(0, 15))
        self.update_preview()

        # Dungeon selection
        dungeon_label = tk.Label(self.home_frame, text="Select Dungeon", 
                                font=("Arial", 18, "bold"), bg='#1a1a1a', fg='#ffd700')
        dungeon_label.pack(pady=(10, 10))
        
        dungeon_frame = tk.Frame(self.home_frame, bg='#1a1a1a')
        dungeon_frame.pack(pady=5)
        
        dungeon_colors = ['#4a7c59', '#c9302c', '#5bc0de', '#6f42c1']
        dungeon_names = ['Forest Temple', 'Volcano Depths', 'Ice Cavern', 'Shadow Realm']
        for i in range(1, 5):
            btn = tk.Button(dungeon_frame, text=f"🏰 Dungeon {i}\n{dungeon_names[i-1]}", 
                          font=("Arial", 12, "bold"),
                          bg=dungeon_colors[i-1], fg='white', 
                          activebackground=dungeon_colors[i-1], 
                          command=lambda d=i: self.start_dungeon(d),
                          bd=0, padx=15, pady=12, cursor='hand2', width=15)
            btn.pack(side='left', padx=8)
    
    def create_class_button(self, parent, class_name):
        info = self.CLASS_INFO[class_name]
        
        btn_frame = tk.Frame(parent, bg=info['color'], bd=3, relief='raised')
        btn_frame.pack(side='left', padx=10)
        
        btn = tk.Button(btn_frame, 
                       text=f"{info['emoji']} {class_name}\n\n{info['desc']}", 
                       font=("Arial", 12, "bold"),
                       bg='#2d2d2d', fg=info['color'], 
                       activebackground='#3d3d3d',
                       activeforeground=info['color'],
                       command=lambda: self.choose_class(class_name),
                       bd=0, padx=20, pady=15, cursor='hand2',
                       width=18, height=6, justify='center')
        btn.pack()
    def choose_class(self, cls):
        self.selected_class = cls
        self.class_chosen = True  # mark that class has been chosen
        self.preview_player = Player(self.name_var.get(), cls)
        self.preview_player.unlock_skills()
        self.update_preview()
        # hide buttons
        # Rebuild home to hide class selection buttons
        self.build_home()

    def update_preview(self):
        p = self.preview_player
        lines = [
            f"Name: {p.name}",
            f"Class: {p.class_name}",
            f"Level: {p.level}  XP: {p.xp}/{p.xp_to_next}",
            f"HP: {p.max_hp}   Mana: {p.max_mana}",
            f"STR:{p.strength}  VIT:{p.vitality}  AGI:{p.agility}  CON:{p.constitution}  INT:{p.intelligence}  WIS:{p.wisdom}  WIL:{p.will}",
            "Unlocked Skills: " + (", ".join(sk['name'] for sk in p.unlocked_skills) if p.unlocked_skills else "(none)")
        ]
        self.preview_text.delete('1.0', tk.END)
        self.preview_text.insert(tk.END, "\n".join(lines))

    def quit_to_menu(self):
        if self.game_frame_container:
            player = self.game_frame_container.player
            self.save_player(player.to_dict())
            self.preview_player = player  # update preview with last played player
            self.game_frame_container.destroy()
            self.game_frame_container = None

        self.home_frame.pack(fill='both', expand=True)
        self.build_home()
    def start_dungeon(self, dungeon_id):
        player = Player.from_dict(self.preview_player.to_dict())
        self.home_frame.pack_forget()
        if self.game_frame_container:
            self.game_frame_container.destroy()
        # pass dungeon_id here
        self.game_frame_container = GameFrame(self, player, on_quit_to_menu=self.quit_to_menu, dungeon_id=dungeon_id)
        self.game_frame_container.pack()
    # ---------- Saving / Loading ----------
    def save_player(self,data):
        try:
            with open(self.SAVE_FILE,'w') as f: json.dump(data,f)
        except Exception as e:
            print("Error saving player:", e)

    def load_player(self):
        if os.path.exists(self.SAVE_FILE):
            try:
                with open(self.SAVE_FILE,'r') as f: return json.load(f)
            except Exception as e:
                print("Error loading player:", e)
        return None

if __name__=="__main__":
    app = MainApp()
    app.mainloop()



















