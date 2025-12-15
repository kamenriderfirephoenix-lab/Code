import tkinter as tk
from tkinter import ttk
import random, math, time, json, os
import ctypes
from tkinter import ttk
# Fix blurry text on high-DPI displays while maintaining proper size
try:
    # Tell Windows we'll handle DPI ourselves
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Windows 8.1+
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # Windows Vista+
    except:
        pass  # Not on Windows or already set

# Get the DPI scaling factor to compensat self.update_player(dt)e
try:
    dpi = ctypes.windll.user32.GetDpiForSystem()
    SCALE_FACTOR = dpi / 96.0  # 96 is the default DPI
except:
    SCALE_FACTOR = 1.0

# ---------- Config ----------
WINDOW_W = int(800 * SCALE_FACTOR)
WINDOW_H = int(600 * SCALE_FACTOR)
ROOM_ROWS = 2
ROOM_COLS = 5
MAX_SKILLS = 30
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
    # In Player.__init__, reorder the initialization:

    def __init__(self,name='Hero',class_name='Warrior'):
        self.name=name; self.class_name=class_name
        self.x=WINDOW_W//2; self.y=WINDOW_H//2; self.size=16
        
        # Base stats - Monk gets different starting stats
        if class_name == 'Monk':
            self.strength=5; self.vitality=10; self.agility=5  # +5 VIT
            self.intelligence=-2; self.wisdom=0; self.will=0; self.constitution=3
        else:
            self.strength=5; self.vitality=5; self.agility=5
            self.intelligence=5; self.wisdom=5; self.will=5; self.constitution=3
        
        self.level=1; self.xp=0; self.xp_to_next=100
        self.stat_points=5; self.skill_points=0
        self.skills=[]; self.unlocked_skills=[]
        
        # NEW: Inventory system - MUST BE BEFORE update_stats()
        self.coins = 50
        self.inventory = []
        self.equipped_items = []
        self.soulbound_items = []
        self.last_soulbound_upgrade_level = 0
        
        # Give starting soulbound item FIRST
        self.give_starting_item()
        
        # NOW populate skills and update stats
        self.populate_skills()
        self.update_equipped_skills()  # ADD THIS LINE
        self.update_stats()
        self.hp = self.max_hp
        self.mana = self.max_mana
        self.active_skill_effects = {}
        self.item = None
            
    def update_stats(self):
        """Calculate stats including equipment and soulbound item bonuses"""
        # Base stats from character
        self.max_hp = 50 + self.vitality * 10
        self.hp = min(getattr(self, 'hp', self.max_hp), self.max_hp)
        self.max_mana = 20 + self.intelligence * 10
        self.mana = min(getattr(self, 'mana', self.max_mana), self.max_mana)
        self.base_speed = 2 + self.agility * 0.3
        self.speed = self.base_speed
        self.atk = 5 + self.strength
        self.mag = 2 + self.will
        self.vit = 2 + self.vitality
        self.wis = 2 + self.wisdom
        self.hp_regen = 0.2 + self.vitality * 0.07
        self.mana_regen = 0.1 + self.wisdom * 0.15

        # Create a set to track which items we've already counted
        counted_items = set()

        # Add bonuses from equipped items
        for item in self.equipped_items:
            item_id = id(item)
            if item_id in counted_items:
                continue
            counted_items.add(item_id)
            
            for stat, value in item.stats.items():
                if stat == 'strength':
                    self.atk += value
                elif stat == 'vitality':
                    bonus_hp = value * 10
                    self.max_hp += bonus_hp
                    self.hp = min(self.hp + bonus_hp, self.max_hp)
                    self.vit += value
                    self.hp_regen += value * 0.07
                elif stat == 'agility':
                    self.base_speed += value * 0.3
                    self.speed = self.base_speed
                elif stat == 'intelligence':
                    bonus_mana = value * 10
                    self.max_mana += bonus_mana
                    self.mana = min(self.mana + bonus_mana, self.max_mana)
                elif stat == 'wisdom':
                    self.wis += value
                    self.mana_regen += value * 0.15
                elif stat == 'will':
                    self.mag += value
                elif stat == 'constitution':
                    self.constitution += value

        # Apply soulbound item bonuses ONLY if they're not already equipped
        for item in self.soulbound_items:
            item_id = id(item)
            if item_id in counted_items:
                continue  # Skip if already counted from equipped_items
            counted_items.add(item_id)
            
            for stat, value in item.stats.items():
                if stat == 'strength':
                    self.atk += value
                elif stat == 'vitality':
                    bonus_hp = value * 10
                    self.max_hp += bonus_hp
                    self.hp = min(self.hp + bonus_hp, self.max_hp)
                    self.vit += value
                    self.hp_regen += value * 0.07
                elif stat == 'agility':
                    self.base_speed += value * 0.3
                    self.speed = self.base_speed
                elif stat == 'intelligence':
                    bonus_mana = value * 10
                    self.max_mana += bonus_mana
                    self.mana = min(self.mana + bonus_mana, self.max_mana)
                elif stat == 'wisdom':
                    self.wis += value
                    self.mana_regen += value * 0.15
                elif stat == 'will':
                    self.mag += value
                elif stat == 'constitution':
                    self.constitution += value
    def update_equipped_skills(self):
        """Add skills from equipped items"""
        # Remove item-granted skills first
        self.unlocked_skills = [sk for sk in self.unlocked_skills if not sk.get('from_item')]
        
        # Skill cooldown mapping
        skill_cooldowns = {
            'Flame Strike': 3.0,
            'Ice Arrow': 1.5,
            'Lightning Bolt': 2.5,
            'Life Drain': 4.0,
            'Blink': 5.0,
            'Backstab': 3.0,
            'Dragon Strike': 8.0,
            'Time Warp': 10.0,
            'Mana Beam': 4.0,
            'Dark Slash': 1.0,
            'Shield': 6.0,
            'Heal': 2.0,
            'Arrow Shot': 0.8
        }
        
        # Add skills from ALL equipped items (including soulbound)
        for item in self.equipped_items:
            print(f"DEBUG: Checking item {item.name} for skills: {item.skills}")
            for skill_name in item.skills:
                if skill_name in self.item_skill_functions:
                    skill_func = self.item_skill_functions[skill_name]
                    cooldown = skill_cooldowns.get(skill_name, 2.0)  # Default to 2.0 if not specified
                    new_skill = {
                        'skill': skill_func,
                        'name': skill_name,
                        'key': 0,  # Unassigned by default
                        'level': self.level,
                        'cooldown': cooldown,  # Use specific cooldown
                        'last_used': 0,
                        'cooldown_mod': 1.0,
                        'from_item': True  # Mark as item skill
                    }
                    self.unlocked_skills.append(new_skill)
                    print(f"DEBUG: Added skill {skill_name} from {item.name}")
    def equip_item(self, item):
        """Equip an item - only one item per type allowed"""
        if item not in self.inventory:
            return False
        
        # Unequip any item of the same type
        for equipped in list(self.equipped_items):
            if equipped.item_type == item.item_type:
                self.unequip_item(equipped)
        
        # Add to equipped list (both soulbound and regular items)
        self.equipped_items.append(item)
        
        self.update_stats()
        self.update_equipped_skills()
        return True
    def unequip_item(self, item):
        """Unequip an item"""
        if item in self.equipped_items:
            self.equipped_items.remove(item)
            self.update_stats()
            self.update_equipped_skills()  # ADD THIS LINE
            return True
        return False
            
    def add_item_to_inventory(self, item):
        """Add item to inventory"""
        self.inventory.append(item)
        # Track soulbound items for permanent bonuses
        if item.soulbound and item not in self.soulbound_items:
            self.soulbound_items.append(item)
    
    def remove_item_from_inventory(self, item):
        """Remove item from inventory"""
        if item in self.inventory:
            if item in self.equipped_items:
                self.unequip_item(item)
            self.inventory.remove(item)
            return True
        return False
    
    def die(self):
        """Called when player dies - lose all non-soulbound items"""
        items_to_remove = []
        for item in self.inventory:
            if not item.soulbound:
                items_to_remove.append(item)
        
        for item in items_to_remove:
            self.remove_item_from_inventory(item)
    def give_starting_item(self):
        """Give each class a soulbound weapon"""
        starting_items = {
            'Warrior': {'name': 'Iron Spear', 'type': 'weapon', 'rarity': 'Common', 
                       'stats': {'strength': 1, 'vitality': 1}, 'skills': [], 'weapon_type': 'spear'},
            'Mage': {'name': 'Novice Staff', 'type': 'weapon', 'rarity': 'Common',
                    'stats': {'intelligence': 1, 'wisdom': 1}, 'skills': [], 'weapon_type': 'staff'},
            'Rogue': {'name': 'Shadow Dagger', 'type': 'weapon', 'rarity': 'Common',
                     'stats': {'agility': 1, 'strength': 1}, 'skills': [], 'weapon_type': 'dagger'},
            'Cleric': {'name': 'Holy Staff', 'type': 'weapon', 'rarity': 'Common',
                      'stats': {'will': 1, 'wisdom': 1}, 'skills': [], 'weapon_type': 'wand'},
            'Druid': {'name': 'Nature Staff', 'type': 'weapon', 'rarity': 'Common',
                     'stats': {'wisdom': 1, 'intelligence': 1}, 'skills': [], 'weapon_type': 'quarterstaff'},
            'Monk': {'name': 'Blessed Fists', 'type': 'weapon', 'rarity': 'Common',
                    'stats': {'vitality': 2}, 'skills': [], 'weapon_type': 'hand'},
            'Ranger': {'name': 'Hunter\'s Bow', 'type': 'weapon', 'rarity': 'Common',
                      'stats': {'agility': 1, 'strength': 1}, 'skills': [], 'weapon_type': 'bow'}
        }
        
        item_data = starting_items.get(self.class_name)
        if item_data:
            item = InventoryItem(
                name=item_data['name'],
                item_type=item_data['type'],
                rarity=item_data['rarity'],
                stats=item_data['stats'],
                skills=item_data['skills'],
                soulbound=True,
                weapon_type=item_data.get('weapon_type')
            )
            self.inventory.append(item)
            self.soulbound_items.append(item)
            # Auto-equip the soulbound weapon
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
        def laser(player, game):
            if player.mana < 30:
                return
            player.mana -= 30
            
            # Create or activate beam
            if not hasattr(game, 'player_beam') or game.player_beam is None:
                # Find nearest enemy for initial angle
                if game.room.enemies:
                    target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
                    angle = math.atan2(target.y - player.y, target.x - player.x)
                else:
                    angle = 0
                
                game.player_beam = Beam(
                    player.x, player.y,
                    angle, 500, 'yellow', 12, owner=player
                )
                game.beam_active_until = time.time() + 3.0 + player.mag / 10# 3 second duration

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


        def lingering_aura_of_valour(player, game):
            duration_ms = 3000   # 3 seconds
            tick_ms = 15         # update every 0.015s
            mana_cost_per_tick = 0.1

            def rapid_tick():
                if player.mana <= 0 or time.time() >= player._rapid_end:
                    player._rapid_active = False
                    return

                player.mana -= mana_cost_per_tick
                game.spawn_particle(player.x, player.y, 35, 'yellow', life=0.5, rtype="aura")

                # Damage nearby enemies
                for e in list(game.room.enemies):
                    if distance((player.x, player.y), (e.x, e.y)) < 50:
                        game.damage_enemy(e, player.atk / 2)

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
            offset = arc_radius // 1.5   # half the radius forward
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
            arc_radius = 40          # reach
            arc_width = math.pi / 3  # angular width

            # Offset origin forward so blade appears in front
            offset = arc_radius // 2
            origin_x = player.x + math.cos(angle_center) * offset
            origin_y = player.y + math.sin(angle_center) * offset

            # Spawn blade particle at the same origin used for damage math
            blade_particle = Particle(
                origin_x, origin_y,
                arc_radius,
                'purple',
                life=0.3,
                rtype='blade',
                angle=angle_center,
                damage=0  # visual only
            )
            game.particles.append(blade_particle)

            # Damage enemies in the arc sector
            for e in list(game.room.enemies):
                dx, dy = e.x - origin_x, e.y - origin_y
                dist = math.hypot(dx, dy)
                if dist <= arc_radius + e.size:
                    angle_to_enemy = math.atan2(dy, dx)
                    diff = (angle_to_enemy - angle_center + 2 * math.pi) % (2 * math.pi)
                    if diff <= arc_width / 2 or diff >= 2 * math.pi - arc_width / 2:
                        game.damage_enemy(e, player.atk * 1.5)

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

        def speed_boost(player, game):
            """Rogue skill: temporary speed buff"""
            if player.mana < 10:
                return
            player.mana -= 10
            
            # Store original speed multiplier
            duration = 2.0  # 5 seconds
            speed_multiplier = 10
            
            # Apply speed boost
            player.speed = player.base_speed * speed_multiplier
            
            # Visual effect
            for _ in range(12):
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(0, 25)
                px = player.x + math.cos(angle) * dist
                py = player.y + math.sin(angle) * dist
                game.spawn_particle(px, py, 6, 'purple', life=0.8)
            
            # Schedule speed reset
            def reset_speed():
                player.speed = player.base_speed
            
            game.after(int(duration * 1000), reset_speed)
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
        # Item-granted skills
        def mana_beam(player, game):
            if player.mana < 25:
                return
            player.mana -= 25
            
            # Create or activate beam
            if not hasattr(game, 'player_beam') or game.player_beam is None:
                # Find nearest enemy for initial angle
                if game.room.enemies:
                    target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
                    angle = math.atan2(target.y - player.y, target.x - player.x)
                else:
                    angle = 0
                
                game.player_beam = Beam(
                    player.x, player.y,
                    angle, 400, 'cyan', 10, owner=player
                )
                game.beam_active_until = time.time() + 2.5 + player.mag / 15  # 2.5 second duration
        def flame_strike(player, game):
            if player.mana < 15 or not game.room.enemies:
                return
            player.mana -= 15
            
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            angle_center = math.atan2(target.y - player.y, target.x - player.x)
            
            # Fire slash visual effect - large arc
            arc_radius = 80
            num_particles = 40
            arc_width = math.pi / 2
            
            for i in range(num_particles):
                angle = angle_center - arc_width/2 + (i / (num_particles-1)) * arc_width
                x = player.x + math.cos(angle) * arc_radius * random.uniform(0.8, 1.2)
                y = player.y + math.sin(angle) * arc_radius * random.uniform(0.8, 1.2)
                
                # Create flame particles with varied life
                flame = Particle(
                    x, y, 
                    size=random.uniform(8, 15), 
                    color=random.choice(['orange', 'red', 'yellow']),
                    life=random.uniform(0.5, 1.0),
                    owner="player",
                    rtype="flame"
                )
                game.particles.append(flame)
            
            # Damage enemies in arc
            for e in list(game.room.enemies):
                dx = e.x - player.x
                dy = e.y - player.y
                dist = math.hypot(dx, dy)
                if dist <= arc_radius:
                    angle_to_enemy = math.atan2(dy, dx)
                    diff = (angle_to_enemy - angle_center + math.pi*2) % (math.pi*2)
                    if diff < arc_width/2 or diff > math.pi*2 - arc_width/2:
                        game.damage_enemy(e, player.atk * 3)
            
        def ice_arrow(player, game):
            if player.mana < 10 or not game.room.enemies:
                return
            player.mana -= 10
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            ang = math.atan2(target.y - player.y, target.x - player.x)
            game.spawn_projectile(player.x, player.y, ang, 10, 3, 8, 'cyan', player.mag * 2, 'player', ptype='icicle', stype='bolt1')
        
        def lightning_bolt(player, game):
            if player.mana < 20 or not game.room.enemies:
                return
            player.mana -= 20
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            ang = math.atan2(target.y - player.y, target.x - player.x)
            game.spawn_projectile(player.x, player.y, ang, 15, 2, 12, 'yellow', player.mag * 4, 'player', stype='lightning')
        
        def life_drain(player, game):
            if player.mana < 25:
                return
            player.mana -= 25
            for e in game.room.enemies:
                if distance((player.x, player.y), (e.x, e.y)) < 100:
                    damage = player.atk * 2
                    game.damage_enemy(e, damage)
                    player.hp = min(player.max_hp, player.hp + damage // 2)
        
        def blink(player, game):
            if player.mana < 30 or not game.room.enemies:
                return
            player.mana -= 30
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            angle = math.atan2(target.y - player.y, target.x - player.x)
            blink_dist = 150
            player.x += math.cos(angle) * blink_dist
            player.y += math.sin(angle) * blink_dist
            player.x = clamp(player.x, 0, WINDOW_W)
            player.y = clamp(player.y, 0, WINDOW_H)
        
        def backstab(player, game):
            if player.mana < 20 or not game.room.enemies:
                return
            player.mana -= 20
            target = min(game.room.enemies, key=lambda e: distance((player.x, player.y), (e.x, e.y)))
            if distance((player.x, player.y), (target.x, target.y)) < 50:
                game.damage_enemy(target, player.atk * 5)
        
        def dragon_strike_item(player, game):
            if player.mana < 50:
                return
            player.mana -= 50
            for e in list(game.room.enemies):
                if distance((player.x, player.y), (e.x, e.y)) < 200:
                    game.damage_enemy(e, player.atk * 3)
        
        def time_warp(player, game):
            if player.mana < 40:
                return
            player.mana -= 40
            # Slow all enemies for 5 seconds
            for e in game.room.enemies:
                e.spd *= 0.3
            game.after(5000, lambda: [setattr(e, 'spd', e.base_spd) for e in game.room.enemies if e in game.room.enemies])
        
        # Store item skill functions for lookup
        self.item_skill_functions = {
            'Flame Strike': flame_strike,
            'Ice Arrow': ice_arrow,
            'Lightning Bolt': lightning_bolt,
            'Life Drain': life_drain,
            'Blink': blink,
            'Backstab': backstab,
            'Dragon Strike': dragon_strike_item,
            'Time Warp': time_warp,
            'Mana Beam': mana_beam,
            'Dark Slash': dark_slash,
            'Shield': mana_shield,
            'Heal': minor_heal,
            'Arrow Shot': arrow_shot
        }
        # Assign skills based on class
        self.skills.clear()
        if self.class_name=='Mage':
            self.skills.append({'skill': mana_bolt,'name':'Mana Bolt','key':1,'level':1,'cooldown':0.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': mana_shield,'name':'Mana Bubble','key':0,'level':5,'cooldown':2,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': fireball,'name':'Fireball','key':0,'level':10,'cooldown':1.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': icicle,'name':'Icicle','key':0,'level':10,'cooldown':1.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': chain_lightning,'name':'Chain Lightning','key':0,'level':15,'cooldown':2,'last_used':0,'cooldown_mod':1.0})
        elif self.class_name=='Warrior':
            self.skills.append({'skill': strike,'name':'Strikes','key':1,'level':1,'cooldown':0.2,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': ground_pound,'name':'Ground Pound','key':0,'level':5,'cooldown':0.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': fist_blast,'name':'Fist Blast','key':0,'level':10,'cooldown':1,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': lingering_aura_of_valour,'name':'Lingering Aura of Valour','key':0,'level':15,'cooldown':2,'last_used':0,'cooldown_mod':1.0})
        elif self.class_name=='Rogue':
            self.skills.append({'skill': dark_slash,'name':'Dark Slash','key':1,'level':1,'cooldown':0.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': shadow_dagger,'name':'Shadow Dagger','key':0,'level':5,'cooldown':0.4,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': speed_boost,'name':'Speed Boost','key':0,'level':10,'cooldown':3,'last_used':0,'cooldown_mod':1.0})
        elif self.class_name=='Cleric':
            self.skills.append({'skill': light_bolt,'name':'Light Bolt','key':1,'level':1,'cooldown':0.5,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': minor_heal,'name':'Minor Heal','key':0,'level':5,'cooldown':1,'last_used':0,'cooldown_mod':1.0})
            self.skills.append({'skill': laser,'name':'Light Beam','key':0,'level':10,'cooldown':2,'last_used':0,'cooldown_mod':1.0})
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
            self.unlock_skills()
            # Upgrade soulbound items every 5 levels
            if self.level % 5 == 0 and self.level > self.last_soulbound_upgrade_level:
                self.upgrade_soulbound_items()
                self.last_soulbound_upgrade_level = self.level
            
            # Unlock soulbound skill every 10 levels
                    # Scale existing enemies in the current room once
                if game:
                    for e in game.room.enemies:
                        if isinstance(e, (Enemy, Boss)):
                            e.scale_with_player(self.level)
                    rescale_room_enemies(game.room, self.level)

        return leveled
    def upgrade_soulbound_items(self):
        """Evolve soulbound weapon at levels 10, 25, 40"""
        # Only evolve at specific levels
        if self.level not in [10, 25, 40]:
            return
        
        # Evolution data for each class
        evolutions = {
            'Warrior': {
                10: {'name': 'Spear of Valour', 'stats': {'strength': 3, 'vitality': 3}, 'skills': ['Flame Strike']},
                25: {'name': 'Legendary Spear', 'stats': {'strength': 6, 'vitality': 6}, 'skills': ['Flame Strike', 'Life Drain']},
                40: {'name': 'Divine Spear', 'stats': {'strength': 10, 'vitality': 10}, 'skills': ['Flame Strike', 'Life Drain', 'Dragon Strike']}
            },
            'Mage': {
                10: {'name': 'Arcane Staff', 'stats': {'intelligence': 3, 'wisdom': 3}, 'skills': ['Mana Beam']},
                25: {'name': 'Staff of Power', 'stats': {'intelligence': 6, 'wisdom': 6}, 'skills': ['Lightning Bolt', 'Time Warp']},
                40: {'name': 'Staff of Eternity', 'stats': {'intelligence': 10, 'wisdom': 10}, 'skills': ['Lightning Bolt', 'Time Warp', 'Ice Arrow']}
            },
            'Rogue': {
                10: {'name': 'Assassin Dagger', 'stats': {'agility': 3, 'strength': 3}, 'skills': ['Backstab']},
                25: {'name': 'Void Dagger', 'stats': {'agility': 6, 'strength': 6}, 'skills': ['Backstab', 'Blink']},
                40: {'name': 'Eternal Blade', 'stats': {'agility': 10, 'strength': 10}, 'skills': ['Backstab', 'Blink', 'Life Drain']}
            },
            'Cleric': {
                10: {'name': 'Divine Staff', 'stats': {'will': 3, 'wisdom': 3}, 'skills': ['Lightning Bolt']},
                25: {'name': 'Staff of Blessing', 'stats': {'will': 6, 'wisdom': 6}, 'skills': ['Lightning Bolt', 'Life Drain']},
                40: {'name': 'Celestial Rod', 'stats': {'will': 10, 'wisdom': 10}, 'skills': ['Lightning Bolt', 'Life Drain', 'Time Warp']}
            },
            'Druid': {
                10: {'name': 'Grove Staff', 'stats': {'wisdom': 3, 'intelligence': 3}, 'skills': ['Ice Arrow']},
                25: {'name': 'Ancient Staff', 'stats': {'wisdom': 6, 'intelligence': 6}, 'skills': ['Ice Arrow', 'Lightning Bolt']},
                40: {'name': 'World Tree Branch', 'stats': {'wisdom': 10, 'intelligence': 10}, 'skills': ['Ice Arrow', 'Lightning Bolt', 'Flame Strike']}
            },
            'Monk': {
                10: {'name': 'Iron Fists', 'stats': {'vitality': 4}, 'skills': ['Flame Strike']},
                25: {'name': 'Dragon Fists', 'stats': {'vitality': 8}, 'skills': ['Flame Strike', 'Life Drain']},
                40: {'name': 'Fists of Heaven', 'stats': {'vitality': 12}, 'skills': ['Flame Strike', 'Life Drain', 'Dragon Strike']}
            },
            'Ranger': {
                10: {'name': 'Elven Bow', 'stats': {'agility': 3, 'strength': 3}, 'skills': ['Ice Arrow']},
                25: {'name': 'Bow of the Wild', 'stats': {'agility': 6, 'strength': 6}, 'skills': ['Ice Arrow', 'Flame Strike']},
                40: {'name': 'Legendary Longbow', 'stats': {'agility': 10, 'strength': 10}, 'skills': ['Ice Arrow', 'Flame Strike', 'Lightning Bolt']}
            }
        }
        
        # Check if evolution exists for this level
        class_evolutions = evolutions.get(self.class_name, {})
        evolution_data = class_evolutions.get(self.level)
        
        if not evolution_data:
            return
        
        # Find and update the soulbound weapon in INVENTORY (the actual reference used)
        weapon = None
        for item in self.inventory:
            if item.soulbound and item.item_type == 'weapon':
                weapon = item
                break
        
        if not weapon:
            print("ERROR: No soulbound weapon found in inventory!")
            return
        
        # Update weapon properties
        weapon.name = evolution_data['name']
        weapon.stats = evolution_data['stats'].copy()
        weapon.skills = evolution_data['skills'].copy()
        
        print(f"⭐ {weapon.name} has evolved! New power unlocked!")
        print(f"⭐ New skills available: {', '.join(weapon.skills)}")
        
        # Update soulbound_items list to point to the correct weapon
        self.soulbound_items = [item for item in self.inventory if item.soulbound]
        
        # Force refresh equipped skills
        self.update_equipped_skills()
        
        # Always update stats
        self.update_stats()
           
    def unlock_skills(self):
        for sk in self.skills:
            if sk['level']<=self.level and sk not in self.unlocked_skills:
                if len(self.unlocked_skills)<MAX_SKILLS:
                    self.unlocked_skills.append(sk)
    def assign_weapon(self):
        """Assign appropriate weapon based on class"""
        if self.class_name == "Warrior":
            self.item = Item(self.x, self.y, 'spear', 'silver', 20, owner=self)
        elif self.class_name == "Mage":
            self.item = Item(self.x, self.y, 'staff', 'blue', 22, owner=self)
            self.item.gem_color = 'cyan'
        elif self.class_name == "Rogue":
            self.item = Item(self.x, self.y, 'dagger', 'purple', 18, owner=self)
        elif self.class_name == "Cleric":
            self.item = Item(self.x, self.y, 'wand', 'gold', 22, owner=self)
            self.item.gem_color = 'yellow'
        elif self.class_name == "Druid":
            self.item = Item(self.x, self.y, 'quarterstaff', 22, owner=self)
            self.item.gem_color = 'lime'
        elif self.class_name == "Monk":
            self.item = Item(self.x, self.y, 'hand', '#FFA500', 20, owner=self)
        elif self.class_name == "Ranger":
            self.item = Item(self.x, self.y, 'bow', 'brown', 18, owner=self)
    

    # Unlocking soulbound skill
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
            "coins": self.coins,
            "inventory": [item.to_dict() for item in self.inventory],
            "soulbound_items": [item.name for item in self.soulbound_items],
            "last_soulbound_upgrade_level": self.last_soulbound_upgrade_level,
            "equipped_items": [item.name for item in self.equipped_items],
            "unlocked_skills": [sk['name'] for sk in self.unlocked_skills],
            "active_skill_effects": self.active_skill_effects,
            "active_skills": [
                {
                    "name": sk['name'],
                    "key": sk['key'],
                    "cooldown": sk['cooldown'],
                    "last_used": sk['last_used'],
                    "cooldown_mod": sk.get('cooldown_mod', 1.0)
                }
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
        p.coins = data.get('coins', 0)
        
        # Load inventory
        p.inventory.clear()
        for item_data in data.get('inventory', []):
            p.inventory.append(InventoryItem.from_dict(item_data))
        
        # Load equipped items
        equipped_names = data.get('equipped_items', [])
        for item in p.inventory:
            if item.name in equipped_names:
                p.equipped_items.append(item)
        # Load soulbound items
        soulbound_names = data.get('soulbound_items', [])
        for item in p.inventory:
            if item.name in soulbound_names:
                p.soulbound_items.append(item)
        p.last_soulbound_upgrade_level = data.get('last_soulbound_upgrade_level', 0)
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
        saved_active = data.get("active_skills", [])
        for act in saved_active:
            for sk in p.unlocked_skills:
                if sk["name"] == act["name"]:
                    sk["key"] = act["key"]
                    sk["cooldown"] = act["cooldown"]
                    sk["last_used"] = act["last_used"]
                    sk["cooldown_mod"] = act.get("cooldown_mod", 1.0)
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
        if self.class_name == 'Monk':
            self.strength=5; self.vitality=10; self.agility=5
            self.intelligence=0; self.wisdom=0; self.will=0; self.constitution=3
        else:
            self.strength=5; self.vitality=5; self.agility=5
            self.intelligence=5; self.wisdom=5; self.will=5; self.constitution=3

        # Clear skills and repopulate for class
        self.skills.clear()
        self.unlocked_skills.clear()
        self.populate_skills()
        self.unlock_skills()
        
        # Reset inventory and equipment
        self.inventory.clear()
        self.equipped_items.clear()
        self.soulbound_items.clear()
        self.coins = 0
        
        # Reset soulbound upgrade tracking
        self.last_soulbound_upgrade_level = 0
        
        # Give fresh starting soulbound item
        self.give_starting_item()

        # Reset HP/Mana
        self.update_stats()
        self.hp = self.max_hp
        self.mana = self.max_mana
# ---------- Enemy/Boss/Projectile/Particle ----------
# ---------- Item System ----------

import math

class Item:
    def __init__(self, x, y, item_type='sword', color='gray', size=20, angle=0, owner=None):
        self.x = x
        self.y = y
        self.item_type = item_type
        self.color = color
        self.size = size
        self.angle = angle
        self.owner = owner
        self.gem_color = 'cyan'
        
    def update(self, owner_x, owner_y, target_x, target_y):
        """Update item position and rotation to face target"""
        self.x = owner_x
        self.y = owner_y
        self.angle = math.atan2(target_y - owner_y, target_x - owner_x)
    
    def draw(self, canvas):
        if self.item_type == 'sword':
            self.draw_sword(canvas)
        elif self.item_type == 'spear':
            self.draw_spear(canvas)
        elif self.item_type == 'bow':
            self.draw_bow(canvas)
        elif self.item_type == 'staff':
            self.draw_staff(canvas)
        elif self.item_type == 'hand':
            self.draw_hand(canvas)
        elif self.item_type == 'dagger':
            self.draw_dagger(canvas)
        elif self.item_type == 'wand':
            self.draw_wand(canvas)
        elif self.item_type == 'quarterstaff':
            self.draw_quarterstaff(canvas)
        elif self.item_type == 'axe':
            self.draw_axe(canvas)
        elif self.item_type == 'scythe':
            self.draw_scythe(canvas)
        elif self.item_type == 'katana':
            self.draw_katana(canvas)
    def draw_wand(self, canvas):
        """Shorter, thinner staff with small circular gem"""
        staff_len = self.size * 1.8  # shorter than staff
        
        forward_offset = 5
        center_x = self.x + math.cos(self.angle) * forward_offset
        center_y = self.y + math.sin(self.angle) * forward_offset
        
        back_fraction = 0.3
        front_fraction = 0.7
        staff_end_x = center_x - math.cos(self.angle) * staff_len * back_fraction
        staff_end_y = center_y - math.sin(self.angle) * staff_len * back_fraction
        gem_x = center_x + math.cos(self.angle) * staff_len * front_fraction
        gem_y = center_y + math.sin(self.angle) * staff_len * front_fraction
        
        # Very thin shaft
        canvas.create_line(staff_end_x+1, staff_end_y+1, gem_x+1, gem_y+1,
                           fill='#2F4F4F', width=4)
        canvas.create_line(staff_end_x, staff_end_y, gem_x, gem_y,
                           fill='#654321', width=3)
        canvas.create_line(staff_end_x, staff_end_y, gem_x, gem_y,
                           fill='#8B4513', width=2)
        
        # Small circular gem
        gem_radius = 5
        canvas.create_oval(gem_x - gem_radius, gem_y - gem_radius,
                          gem_x + gem_radius, gem_y + gem_radius,
                          fill=self.gem_color, outline='gold', width=1)
        # Inner glow
        canvas.create_oval(gem_x - gem_radius//2, gem_y - gem_radius//2,
                          gem_x + gem_radius//2, gem_y + gem_radius//2,
                          fill='white', outline='')

    def draw_quarterstaff(self, canvas):
        """Long wooden staff with metal caps - THINNER VERSION"""
        staff_len = self.size * 3.5
        
        forward_offset = 5
        center_x = self.x + math.cos(self.angle) * forward_offset
        center_y = self.y + math.sin(self.angle) * forward_offset
        
        end1_x = center_x - math.cos(self.angle) * staff_len * 0.5
        end1_y = center_y - math.sin(self.angle) * staff_len * 0.5
        end2_x = center_x + math.cos(self.angle) * staff_len * 0.5
        end2_y = center_y + math.sin(self.angle) * staff_len * 0.5
        
        # Main shaft - MUCH THINNER
        canvas.create_line(end1_x+1, end1_y+1, end2_x+1, end2_y+1,
                           fill='#2F4F4F', width=5)  # Shadow
        canvas.create_line(end1_x, end1_y, end2_x, end2_y,
                           fill='#654321', width=4)  # Outer wood
        canvas.create_line(end1_x, end1_y, end2_x, end2_y,
                           fill='#8B4513', width=2)  # Inner highlight
        
        # Metal caps on both ends - smaller
        for end_x, end_y in [(end1_x, end1_y), (end2_x, end2_y)]:
            canvas.create_oval(end_x-4, end_y-4, end_x+4, end_y+4,
                              fill='#C0C0C0', outline='#696969', width=1)
        
        # Grip wrapping in middle - smaller
        for i in range(-2, 3):
            wrap_x = center_x + math.cos(self.angle) * i * 6
            wrap_y = center_y + math.sin(self.angle) * i * 6
            canvas.create_oval(wrap_x-2, wrap_y-2, wrap_x+2, wrap_y+2,
                              fill='#654321', outline='')

    def draw_katana(self, canvas):
        """Elegant katana with subtle curvature and proper tip alignment"""
        import math

        # --- Base positions ---
        offset = 20
        start_x = self.x + math.cos(self.angle) * offset
        start_y = self.y + math.sin(self.angle) * offset

        blade_len = self.size * 2.5
        handle_len = self.size * 0.8

        blade_end_x = start_x + math.cos(self.angle) * blade_len
        blade_end_y = start_y + math.sin(self.angle) * blade_len

        handle_start_x = self.x - math.cos(self.angle) * handle_len
        handle_start_y = self.y - math.sin(self.angle) * handle_len

        # --- Handle (wrapped cord) ---
        canvas.create_line(
            handle_start_x, handle_start_y,
            start_x, start_y,
            fill='#1a1a1a', width=6
        )
        canvas.create_line(
            handle_start_x, handle_start_y,
            start_x, start_y,
            fill='#8B0000', width=4
        )

        # Handle wrap texture
        for i in range(6):
            t = i / 6
            wrap_x = handle_start_x + (start_x - handle_start_x) * t
            wrap_y = handle_start_y + (start_y - handle_start_y) * t
            canvas.create_oval(
                wrap_x - 2, wrap_y - 2,
                wrap_x + 2, wrap_y + 2,
                fill='#000000', outline=''
            )

        # --- Tsuba (guard) ---
        guard_size = 5
        perp = self.angle + math.pi / 2

        guard_pts = [
            start_x + math.cos(perp) * guard_size - math.cos(self.angle) * 2,
            start_y + math.sin(perp) * guard_size - math.sin(self.angle) * 2,
            start_x - math.cos(perp) * guard_size - math.cos(self.angle) * 2,
            start_y - math.sin(perp) * guard_size - math.sin(self.angle) * 2,
            start_x - math.cos(perp) * guard_size + math.cos(self.angle) * 2,
            start_y - math.sin(perp) * guard_size + math.sin(self.angle) * 2,
            start_x + math.cos(perp) * guard_size + math.cos(self.angle) * 2,
            start_y + math.sin(perp) * guard_size + math.sin(self.angle) * 2,
        ]

        canvas.create_polygon(
            guard_pts,
            fill='#D4AF37',
            outline='#8B6914',
            width=2
        )

        # --- Blade curve (subtle sori) ---
        curve_offset = blade_len * 0.12
        perp = self.angle - math.pi / 2

        mid_x = (start_x + blade_end_x) / 2 + math.cos(perp) * curve_offset
        mid_y = (start_y + blade_end_y) / 2 + math.sin(perp) * curve_offset

        # Quadratic Bézier blade
        segments = 100
        points = []

        for i in range(segments + 1):
            t = i / segments
            x = (1 - t)**2 * start_x + 2 * (1 - t) * t * mid_x + t**2 * blade_end_x
            y = (1 - t)**2 * start_y + 2 * (1 - t) * t * mid_y + t**2 * blade_end_y
            points.extend([x, y])

        # --- Blade body (thin, katana-like) ---
        canvas.create_line(points, fill='#555555', width=6, smooth=True)   # spine
        canvas.create_line(points, fill='#E0E0E0', width=4, smooth=True)   # body
        canvas.create_line(points, fill='white', width=1, smooth=True)    # edge

        # --- Properly aligned tip ---
        x2, y2 = points[-2], points[-1]
        x1, y1 = points[-4], points[-3]
        tangent_angle = math.atan2(y2 - y1, x2 - x1)

        tip_len = 10
        tip_width = 3

        tip_x = blade_end_x + math.cos(tangent_angle) * tip_len
        tip_y = blade_end_y + math.sin(tangent_angle) * tip_len

        perp = tangent_angle + math.pi / 2

        left_x = blade_end_x + math.cos(perp) * tip_width
        left_y = blade_end_y + math.sin(perp) * tip_width
        right_x = blade_end_x - math.cos(perp) * tip_width
        right_y = blade_end_y - math.sin(perp) * tip_width

        canvas.create_polygon(
            [tip_x, tip_y, left_x, left_y, right_x, right_y],
            fill='#E0E0E0',
            outline='#888888'
        )


    def draw_axe(self, canvas):
        """Improved double-bit Viking axe"""
        import math

        # Base positioning
        offset = 15
        start_x = self.x + math.cos(self.angle) * offset
        start_y = self.y + math.sin(self.angle) * offset

        handle_len = self.size * 2.5
        blade_width = self.size * 1.2
        blade_height = self.size * 0.8

        # Handle endpoints
        handle_end_x = self.x - math.cos(self.angle) * handle_len * 0.4
        handle_end_y = self.y - math.sin(self.angle) * handle_len * 0.4
        
        # Axe head position (pushed forward)
        head_x = start_x + math.cos(self.angle) * (handle_len * 0.3)
        head_y = start_y + math.sin(self.angle) * (handle_len * 0.3)

        perp = self.angle + math.pi / 2

        # --- Draw Handle ---
        canvas.create_line(
            handle_end_x, handle_end_y, head_x, head_y,
            fill='#2F4F4F', width=10
        )
        canvas.create_line(
            handle_end_x, handle_end_y, head_x, head_y,
            fill='#654321', width=8
        )
        canvas.create_line(
            handle_end_x, handle_end_y, head_x, head_y,
            fill='#8B4513', width=6
        )

        # Pommel
        canvas.create_oval(
            handle_end_x - 7, handle_end_y - 7,
            handle_end_x + 7, handle_end_y + 7,
            fill='#B8860B', outline='#8B6914', width=2
        )

        # --- Draw Double Blades ---
        for side in [1, -1]:  # Top and bottom blades
            # Blade extends perpendicular to handle
            blade_tip_x = head_x + math.cos(perp) * blade_width * side
            blade_tip_y = head_y + math.sin(perp) * blade_width * side
            
            # Blade back edges (along handle direction)
            back_top_x = head_x + math.cos(self.angle) * blade_height
            back_top_y = head_y + math.sin(self.angle) * blade_height
            back_bot_x = head_x - math.cos(self.angle) * blade_height
            back_bot_y = head_y - math.sin(self.angle) * blade_height
            
            # Inner connection point (close to handle)
            inner_x = head_x + math.cos(perp) * (self.size * 0.25) * side
            inner_y = head_y + math.sin(perp) * (self.size * 0.25) * side

            # Create blade polygon (crescent shape)
            blade_points = [
                back_top_x, back_top_y,      # Back top
                blade_tip_x, blade_tip_y,    # Tip
                back_bot_x, back_bot_y,      # Back bottom
                inner_x, inner_y             # Inner connection
            ]

            # Draw blade with shadow
            canvas.create_polygon(
                blade_points,
                fill='#A9A9A9',
                outline='#696969',
                width=2
            )
            
            # Sharp edge highlight
            canvas.create_line(
                back_top_x, back_top_y,
                blade_tip_x, blade_tip_y,
                fill='#E0E0E0',
                width=3
            )
            canvas.create_line(
                back_top_x, back_top_y,
                blade_tip_x, blade_tip_y,
                fill='white',
                width=1
            )

    def draw_scythe(self, canvas):
        """Death's scythe with inward-curving blade"""
        import math

        handle_len = self.size * 3.2
        blade_len = self.size * 1.2  # smaller blade

        # Offset forward a bit
        forward_offset = 5
        center_x = self.x + math.cos(self.angle) * forward_offset
        center_y = self.y + math.sin(self.angle) * forward_offset

        # Handle positions
        handle_start_x = center_x - math.cos(self.angle) * handle_len * 0.5
        handle_start_y = center_y - math.sin(self.angle) * handle_len * 0.5
        handle_end_x = center_x + math.cos(self.angle) * handle_len * 0.5
        handle_end_y = center_y + math.sin(self.angle) * handle_len * 0.5

        # Draw handle
        canvas.create_line(handle_start_x+1, handle_start_y+1, handle_end_x+1, handle_end_y+1, fill='#2F4F4F', width=6)
        canvas.create_line(handle_start_x, handle_start_y, handle_end_x, handle_end_y, fill='#2C1810', width=5)
        canvas.create_line(handle_start_x, handle_start_y, handle_end_x, handle_end_y, fill='#3D2817', width=3)

        # Ferrule
        canvas.create_oval(handle_end_x-5, handle_end_y-5, handle_end_x+5, handle_end_y+5,
                           fill='#404040', outline='#202020', width=2)

        # --- INWARD CURVE FIX ---
        perp_angle = self.angle - math.pi / 2  # flipped inward

        # Control point (mid-curve)
        blade_mid_x = handle_end_x + math.cos(perp_angle) * blade_len * 0.55
        blade_mid_y = handle_end_y + math.sin(perp_angle) * blade_len * 0.55

        # End point (slightly rotated inward)
        blade_end_x = handle_end_x + math.cos(perp_angle + 0.25) * blade_len
        blade_end_y = handle_end_y + math.sin(perp_angle + 0.25) * blade_len

        # Quadratic bezier points
        segments = 15
        blade_points = []
        for i in range(segments + 1):
            t = i / segments
            x = (1-t)**2 * handle_end_x + 2*(1-t)*t * blade_mid_x + t**2 * blade_end_x
            y = (1-t)**2 * handle_end_y + 2*(1-t)*t * blade_mid_y + t**2 * blade_end_y
            blade_points.extend([x, y])

        # Blade shading
        canvas.create_line(blade_points, fill='#202020', width=10, smooth=True)
        canvas.create_line(blade_points, fill='#606060', width=8, smooth=True)
        canvas.create_line(blade_points, fill='#A0A0A0', width=6, smooth=True)

        # Inner sharp edge (offset inward)
        inner_points = []
        for i in range(segments + 1):
            t = i / segments
            x = (1-t)**2 * handle_end_x + 2*(1-t)*t * blade_mid_x + t**2 * blade_end_x
            y = (1-t)**2 * handle_end_y + 2*(1-t)*t * blade_mid_y + t**2 * blade_end_y

            # perpendicular to blade direction
            perp = math.atan2(blade_end_y - handle_end_y, blade_end_x - handle_end_x) - math.pi / 2
            x -= math.cos(perp) * 2
            y -= math.sin(perp) * 2

            inner_points.extend([x, y])

        canvas.create_line(inner_points, fill='white', width=2, smooth=True)

        # Sharp tip
        tip_angle = math.atan2(blade_end_y - blade_mid_y, blade_end_x - blade_mid_x)
        tip_len = 6
        tip_x = blade_end_x + math.cos(tip_angle) * tip_len
        tip_y = blade_end_y + math.sin(tip_angle) * tip_len
        perp_tip = tip_angle - math.pi / 2

        tip_pts = [
            tip_x, tip_y,
            blade_end_x + math.cos(perp_tip) * 3, blade_end_y + math.sin(perp_tip) * 3,
            blade_end_x - math.cos(perp_tip) * 3, blade_end_y - math.sin(perp_tip) * 3
        ]

        canvas.create_polygon(tip_pts, fill='#808080', outline='#606060')

    
    def draw_dagger(self, canvas):
        offset = 12  # closer to the body
        start_x = self.x + math.cos(self.angle) * offset
        start_y = self.y + math.sin(self.angle) * offset

        blade_len = self.size * 0.9   # shorter blade
        handle_len = self.size * 0.3  # smaller handle

        blade_end_x = start_x + math.cos(self.angle) * blade_len
        blade_end_y = start_y + math.sin(self.angle) * blade_len

        handle_start_x = self.x - math.cos(self.angle) * handle_len
        handle_start_y = self.y - math.sin(self.angle) * handle_len

        # Handle (slim but visible)
        canvas.create_line(handle_start_x, handle_start_y, start_x, start_y,
                           fill='#654321', width=6)
        canvas.create_line(handle_start_x, handle_start_y, start_x, start_y,
                           fill='#8B4513', width=4)

        # Pommel
        canvas.create_oval(handle_start_x-3, handle_start_y-3,
                           handle_start_x+3, handle_start_y+3,
                           fill='#FFD700', outline='#8B6914', width=1)

        # Tiny crossguard
        cross_angle = self.angle + math.pi/2
        cross_len = 6
        cx1 = start_x + math.cos(cross_angle) * cross_len
        cy1 = start_y + math.sin(cross_angle) * cross_len
        cx2 = start_x - math.cos(cross_angle) * cross_len
        cy2 = start_y - math.sin(cross_angle) * cross_len
        canvas.create_line(cx1, cy1, cx2, cy2, fill='#8B6914', width=3)

        # Blade shaft (much thicker)
        canvas.create_line(start_x+2, start_y+2, blade_end_x+2, blade_end_y+2,
                           fill='#404040', width=10)
        canvas.create_line(start_x, start_y, blade_end_x, blade_end_y,
                           fill='#c0c0c0', width=9)
        canvas.create_line(start_x, start_y, blade_end_x, blade_end_y,
                           fill='white', width=5)

        # Triangular tip (short but wide)
        tip_len = 5
        tip_x = blade_end_x + math.cos(self.angle) * tip_len
        tip_y = blade_end_y + math.sin(self.angle) * tip_len

        perp = self.angle + math.pi/2
        tip_width = 5  # extra wide tip
        left_x = blade_end_x + math.cos(perp) * tip_width
        left_y = blade_end_y + math.sin(perp) * tip_width
        right_x = blade_end_x - math.cos(perp) * tip_width
        right_y = blade_end_y - math.sin(perp) * tip_width

        canvas.create_polygon([tip_x, tip_y, left_x, left_y, right_x, right_y],
                              fill='#c0c0c0', outline='gray')

    def draw_sword(self, canvas):
        offset = 20
        start_x = self.x + math.cos(self.angle) * offset
        start_y = self.y + math.sin(self.angle) * offset

        blade_len = self.size * 2.0
        handle_len = self.size * 0.6

        blade_end_x = start_x + math.cos(self.angle) * blade_len
        blade_end_y = start_y + math.sin(self.angle) * blade_len

        handle_start_x = self.x - math.cos(self.angle) * handle_len
        handle_start_y = self.y - math.sin(self.angle) * handle_len

        # Handle
        canvas.create_line(handle_start_x, handle_start_y, start_x, start_y,
                           fill='#654321', width=7)
        canvas.create_line(handle_start_x, handle_start_y, start_x, start_y,
                           fill='#8B4513', width=5)

        # Pommel
        canvas.create_oval(handle_start_x-4, handle_start_y-4,
                           handle_start_x+4, handle_start_y+4,
                           fill='#FFD700', outline='#8B6914', width=2)

        # Crossguard
        cross_angle = self.angle + math.pi/2
        cross_len = 15
        cx1 = start_x + math.cos(cross_angle) * cross_len
        cy1 = start_y + math.sin(cross_angle) * cross_len
        cx2 = start_x - math.cos(cross_angle) * cross_len
        cy2 = start_y - math.sin(cross_angle) * cross_len
        canvas.create_line(cx1, cy1, cx2, cy2, fill='#8B6914', width=6)
        canvas.create_line(cx1, cy1, cx2, cy2, fill='#FFD700', width=4)

        # Blade shaft
        canvas.create_line(start_x+2, start_y+2, blade_end_x+2, blade_end_y+2,
                           fill='#404040', width=10)
        canvas.create_line(start_x, start_y, blade_end_x, blade_end_y,
                           fill='#c0c0c0', width=8)
        canvas.create_line(start_x, start_y, blade_end_x, blade_end_y,
                           fill='white', width=3)

        # --- Add a triangular tip to make it sharp ---
        tip_len = 10  # how far the point extends
        tip_x = blade_end_x + math.cos(self.angle) * tip_len
        tip_y = blade_end_y + math.sin(self.angle) * tip_len

        perp = self.angle + math.pi/2
        tip_width = 6
        left_x = blade_end_x + math.cos(perp) * tip_width
        left_y = blade_end_y + math.sin(perp) * tip_width
        right_x = blade_end_x - math.cos(perp) * tip_width
        right_y = blade_end_y - math.sin(perp) * tip_width

        canvas.create_polygon([tip_x, tip_y, left_x, left_y, right_x, right_y],
                              fill='#c0c0c0', outline='gray')

    def draw_spear(self, canvas):
        offset = 10
        start_x = self.x + math.cos(self.angle) * offset
        start_y = self.y + math.sin(self.angle) * offset

        shaft_len = self.size * 2.5
        tip_len   = self.size * 0.6   # shorter spear head

        shaft_end_x = self.x - math.cos(self.angle) * shaft_len * 0.4
        shaft_end_y = self.y - math.sin(self.angle) * shaft_len * 0.4

        tip_base_x = start_x + math.cos(self.angle) * shaft_len * 0.6
        tip_base_y = start_y + math.sin(self.angle) * shaft_len * 0.6

        # Shaft (thin pole)
        canvas.create_line(shaft_end_x, shaft_end_y, tip_base_x, tip_base_y,
                           fill='#654321', width=5)
        canvas.create_line(shaft_end_x, shaft_end_y, tip_base_x, tip_base_y,
                           fill='#8B4513', width=3)

        # Spear head tip (smaller)
        tip_x = tip_base_x + math.cos(self.angle) * tip_len
        tip_y = tip_base_y + math.sin(self.angle) * tip_len

        perp_angle = self.angle + math.pi/2
        side_len = 5   # narrower sides
        left_x = tip_base_x + math.cos(perp_angle) * side_len
        left_y = tip_base_y + math.sin(perp_angle) * side_len
        right_x = tip_base_x - math.cos(perp_angle) * side_len
        right_y = tip_base_y - math.sin(perp_angle) * side_len

        # Smaller leaf‑shaped spear head
        canvas.create_polygon(
            [tip_x, tip_y, left_x, left_y, tip_base_x, tip_base_y, right_x, right_y],
            fill='#C0C0C0', outline='#696969', width=2
        )

        # Center ridge line
        canvas.create_line(tip_x, tip_y, tip_base_x, tip_base_y,
                           fill='white', width=2)


        
    def draw_bow(self, canvas):
        bow_len = self.size * 1.7
        perp_angle = self.angle + math.pi/2

        # Move bow forward along aim direction
        forward_offset = 5
        bow_center_x = self.x + math.cos(self.angle) * forward_offset
        bow_center_y = self.y + math.sin(self.angle) * forward_offset

        # Swap top/bottom to correct inversion
        top_x = bow_center_x - math.cos(perp_angle) * (bow_len / 2)
        top_y = bow_center_y - math.sin(perp_angle) * (bow_len / 2)
        bot_x = bow_center_x + math.cos(perp_angle) * (bow_len / 2)
        bot_y = bow_center_y + math.sin(perp_angle) * (bow_len / 2)

        # Curve AWAY from the target (reverse sign vs. previous)
        curve_offset = 20
        mid_x = bow_center_x + math.cos(self.angle) * curve_offset
        mid_y = bow_center_y + math.sin(self.angle) * curve_offset

        # Bow limbs
        canvas.create_line(top_x+2, top_y+2, mid_x+2, mid_y+2, bot_x+2, bot_y+2,
                           fill='#2F4F4F', width=7, smooth=True)
        canvas.create_line(top_x, top_y, mid_x, mid_y, bot_x, bot_y,
                           fill='#654321', width=6, smooth=True)
        canvas.create_line(top_x, top_y, mid_x, mid_y, bot_x, bot_y,
                           fill='#8B4513', width=4, smooth=True)

        # Bowstring
        canvas.create_line(top_x, top_y, bot_x, bot_y, fill='#F5F5DC', width=3)

        # Arrow (centered on player so aim stays true)
        arrow_len = self.size * 1.2
        arrow_end_x = self.x + math.cos(self.angle) * arrow_len
        arrow_end_y = self.y + math.sin(self.angle) * arrow_len
        arrow_start_x = self.x - math.cos(self.angle) * 5
        arrow_start_y = self.y - math.sin(self.angle) * 5

        canvas.create_line(arrow_start_x, arrow_start_y, arrow_end_x, arrow_end_y,
                           fill='#8B4513', width=4)

        # Arrow tip
        tip_perp = self.angle + math.pi/2
        tip_len = 8
        tip_left_x = arrow_end_x + math.cos(tip_perp) * (tip_len / 2)
        tip_left_y = arrow_end_y + math.sin(tip_perp) * (tip_len / 2)
        tip_right_x = arrow_end_x - math.cos(tip_perp) * (tip_len / 2)
        tip_right_y = arrow_end_y - math.sin(tip_perp) * (tip_len / 2)
        tip_point_x = arrow_end_x + math.cos(self.angle) * 10
        tip_point_y = arrow_end_y + math.sin(self.angle) * 10
        canvas.create_polygon([tip_point_x, tip_point_y, tip_left_x, tip_left_y,
                               tip_right_x, tip_right_y], fill='gray')

        # Grip (moved forward with bow center)
        canvas.create_oval(bow_center_x-5, bow_center_y-5, bow_center_x+5, bow_center_y+5,
                           fill='#654321', outline='#8B4513', width=2)


    def draw_staff(self, canvas):
        staff_len = self.size * 3   # reduced from 3

        # Move the staff forward along the aim direction
        forward_offset = 5
        center_x = self.x + math.cos(self.angle) * forward_offset
        center_y = self.y + math.sin(self.angle) * forward_offset

        # Compute shaft endpoints relative to the forward-shifted center
        # Slightly bias toward the gem side so more of the staff is visible in front
        back_fraction = 0.35
        front_fraction = 0.65
        staff_end_x = center_x - math.cos(self.angle) * staff_len * back_fraction
        staff_end_y = center_y - math.sin(self.angle) * staff_len * back_fraction
        gem_x       = center_x + math.cos(self.angle) * staff_len * front_fraction
        gem_y       = center_y + math.sin(self.angle) * staff_len * front_fraction

        # Staff shaft shadow
        canvas.create_line(staff_end_x+2, staff_end_y+2, gem_x+2, gem_y+2,
                           fill='#2F4F4F', width=8)
        # Staff shaft outer
        canvas.create_line(staff_end_x, staff_end_y, gem_x, gem_y,
                           fill='#654321', width=7)
        # Staff shaft inner
        canvas.create_line(staff_end_x, staff_end_y, gem_x, gem_y,
                           fill='#8B4513', width=5)

        # Ornamental wrapping
        segments = 6
        for i in range(segments):
            t = i / segments
            wrap_x = staff_end_x + (gem_x - staff_end_x) * t
            wrap_y = staff_end_y + (gem_y - staff_end_y) * t
            canvas.create_oval(wrap_x-3, wrap_y-3, wrap_x+3, wrap_y+3,
                               fill='#FFD700', outline='#8B6914')

        # Gem diamond (shrunk slightly)
        gem_size = 8   # reduced from 15
        # Diamond points
        top_x = gem_x
        top_y = gem_y - gem_size
        right_x = gem_x + gem_size
        right_y = gem_y
        bottom_x = gem_x
        bottom_y = gem_y + gem_size
        left_x = gem_x - gem_size
        left_y = gem_y

        # Outer glow
        canvas.create_polygon(
            top_x, top_y-5, right_x+5, right_y, bottom_x, bottom_y+5, left_x-5, left_y,
            fill=self.gem_color, outline='', stipple='gray50'
        )
        # Middle glow
        canvas.create_polygon(
            top_x, top_y-2, right_x+2, right_y, bottom_x, bottom_y+2, left_x-2, left_y,
            fill=self.gem_color, outline=''
        )
        # Main diamond
        canvas.create_polygon(
            top_x, top_y, right_x, right_y, bottom_x, bottom_y, left_x, left_y,
            fill=self.gem_color, outline='gold', width=1
        )
        # Highlight inner diamond
        canvas.create_polygon(
            gem_x, gem_y - gem_size//2,
            gem_x + gem_size//2, gem_y,
            gem_x, gem_y + gem_size//2,
            gem_x - gem_size//2, gem_y,
            fill='white', outline=''
        )

    def draw_hand(self, canvas):
        """Two smaller fists placed on either side of the body"""
        arm_len = self.size * 1.2   # smaller arms
        fist_size = 6               # smaller fists

        # Perpendicular direction (left/right from facing angle)
        perp_angle = self.angle + math.pi/2

        # Offset distance from body center
        side_offset = 15

        # Loop for left and right hands
        for side in [-1, 1]:
            # Shoulder position offset to the side
            shoulder_x = self.x + math.cos(perp_angle) * side * side_offset
            shoulder_y = self.y + math.sin(perp_angle) * side * side_offset

            # Elbow extends outward
            elbow_x = shoulder_x + math.cos(self.angle) * arm_len * 0.5
            elbow_y = shoulder_y + math.sin(self.angle) * arm_len * 0.5

            # Fist extends farther outward
            fist_x = shoulder_x + math.cos(self.angle) * arm_len
            fist_y = shoulder_y + math.sin(self.angle) * arm_len

            # Upper arm
            canvas.create_line(shoulder_x, shoulder_y, elbow_x, elbow_y,
                               fill=self.color, width=8)

            # Elbow joint
            canvas.create_oval(elbow_x-4, elbow_y-4, elbow_x+4, elbow_y+4,
                               fill=self.color, outline='black', width=2)

            # Forearm
            canvas.create_line(elbow_x, elbow_y, fist_x, fist_y,
                               fill=self.color, width=7)

            # Fist
            canvas.create_oval(fist_x - fist_size, fist_y - fist_size,
                               fist_x + fist_size, fist_y + fist_size,
                               fill=self.color, outline='black', width=2)

            # Knuckles detail
            knuckle_perp = self.angle + math.pi/2
            for offset in [-3, 0, 3]:
                kx = fist_x + math.cos(knuckle_perp) * offset
                ky = fist_y + math.sin(knuckle_perp) * offset
                canvas.create_oval(kx-1, ky-1, kx+1, ky+1,
                                   fill='white', outline='black', width=1)

class Beam(Item):
    def __init__(self, x, y, angle, length, color='red', width=10, owner=None):
        super().__init__(x, y, 'beam', color, width, angle, owner)
        self.length = length
        self.max_length = length
        self.extending = True
        self.growth_speed = 15  # pixels per frame
        self.current_length = 0
        self.origin_x = x
        self.origin_y = y
        
    def update_origin(self, x, y):
        """Update beam origin to follow owner"""
        self.origin_x = x
        self.origin_y = y
    
    def rotate(self, delta_angle):
        """Rotate the beam by delta_angle"""
        self.angle += delta_angle
    def rotate_beam(self, delta_angle):
        if hasattr(self, "player_beam") and self.player_beam:
            self.player_beam.rotate(delta_angle)

    def update(self, dt):
        """Extend or retract beam"""
        if self.extending:
            self.current_length = min(self.current_length + self.growth_speed, self.max_length)
            if self.current_length >= self.max_length:
                self.extending = False

        
    def draw(self, canvas):
        """Draw beam from origin"""
        end_x = self.origin_x + math.cos(self.angle) * self.current_length
        end_y = self.origin_y + math.sin(self.angle) * self.current_length
        
        # Draw beam with gradient effect (multiple lines)
        for i in range(3):
            width = self.size - i * 2
            alpha_color = self.color if i == 0 else self.lighten_color(self.color)
            canvas.create_line(self.origin_x, self.origin_y, end_x, end_y,
                             fill=alpha_color, width=max(1, width))
    
    def lighten_color(self, color):
        """Simple color lightening for visual effect"""
        if color == 'red':
            return '#ff6666'
        elif color == 'blue':
            return '#6666ff'
        elif color == 'green':
            return '#66ff66'
        return color
# Add after the Item class
class InventoryItem:
    """Items that can be bought, equipped, and provide stat/skill buffs"""
    
    RARITY_COLORS = {
        'Common': '#9d9d9d',
        'Uncommon': '#1eff00',
        'Rare': '#0070dd',
        'Epic': '#a335ee',
        'Legendary': '#ff8000'
    }
    
    def __init__(self, name, item_type, rarity, stats=None, skills=None, soulbound=False, price=0, weapon_type=None):
        self.name = name
        self.item_type = item_type  # 'ring', 'necklace', 'armor', 'weapon', etc.
        self.rarity = rarity
        self.stats = stats or {}  # {'strength': 5, 'vitality': 3}
        self.skills = skills or []  # list of skill names this item grants
        self.soulbound = soulbound
        self.price = price
        self.weapon_type = weapon_type  # 'sword', 'spear', 'bow', 'staff', etc.
            
    
    def get_color(self):
        return self.RARITY_COLORS.get(self.rarity, '#ffffff')
    
    def get_description(self):
        """Generate item description"""
        lines = []
        if self.stats:
            for stat, value in self.stats.items():
                lines.append(f"+{value} {stat.upper()}")
        if self.skills:
            lines.append("Skills: " + ", ".join(self.skills))
        if self.soulbound:
            lines.append("[SOULBOUND]")
        return "\n".join(lines)
    
    def to_dict(self):
        return {
            'name': self.name,
            'item_type': self.item_type,
            'rarity': self.rarity,
            'stats': self.stats,
            'skills': self.skills,
            'soulbound': self.soulbound,
            'price': self.price,
            'weapon_type': self.weapon_type  # ADD THIS
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'],
            item_type=data['item_type'],
            rarity=data['rarity'],
            stats=data.get('stats', {}),
            skills=data.get('skills', []),
            soulbound=data.get('soulbound', False),
            price=data.get('price', 0),
            weapon_type=data.get('weapon_type')  # ADD THIS
        )

# Shop inventory - add after InventoryItem class
SHOP_ITEMS = [
    # Common items
    InventoryItem('Iron Ring', 'ring', 'Common', {'strength': 2}, price=50),
    InventoryItem('Copper Necklace', 'necklace', 'Common', {'vitality': 2}, price=50),
    InventoryItem('Swift Band', 'ring', 'Common', {'agility': 2}, price=50),
    
    # Uncommon items
    InventoryItem('Steel Ring', 'ring', 'Uncommon', {'strength': 4, 'vitality': 2}, price=150),
    InventoryItem('Sage\'s Amulet', 'necklace', 'Uncommon', {'intelligence': 4, 'wisdom': 2}, price=150),
    InventoryItem('Hunter\'s Band', 'ring', 'Uncommon', {'agility': 5}, price=150),
    
    # Rare items
    InventoryItem('Titan Ring', 'ring', 'Rare', {'strength': 7, 'vitality': 5}, price=400),
    InventoryItem('Archmage Pendant', 'necklace', 'Rare', {'intelligence': 8, 'will': 4}, price=400),
    InventoryItem('Shadow Cloak Ring', 'ring', 'Rare', {'agility': 8, 'strength': 3}, price=400),
    
    # Epic items
    InventoryItem('Dragon Band', 'ring', 'Epic', {'strength': 12, 'vitality': 8, 'constitution': 3}, price=1000),
    InventoryItem('Celestial Amulet', 'necklace', 'Epic', {'intelligence': 12, 'wisdom': 8, 'will': 5}, price=1000),
    
    # Legendary items
    InventoryItem('Ring of the Immortal', 'ring', 'Legendary', 
                 {'strength': 15, 'vitality': 15, 'constitution': 10}, price=3000),
    InventoryItem('Amulet of Eternity', 'necklace', 'Legendary',
                 {'intelligence': 15, 'wisdom': 15, 'will': 10}, price=3000)
]
# Additional shop items with skills
# Additional shop items with skills
SHOP_ITEMS.extend([
    InventoryItem('Reinforced Bow', 'weapon', 'Uncommon', 
                 {'strength': 4, 'agility': 4}, 
                 skills=['Arrow Shot'], 
                 price=200, 
                 weapon_type='bow'),
    # Rare weapons with skills
    InventoryItem('Flameblade', 'weapon', 'Rare', 
                 {'strength': 8, 'will': 5}, 
                 skills=['Flame Strike'], 
                 price=600, 
                 weapon_type='katana'),  # ALREADY HAS weapon_type
    
    InventoryItem('Frostbite Bow', 'weapon', 'Rare',
                 {'agility': 7, 'intelligence': 4},
                 skills=['Ice Arrow'],
                 price=600,
                 weapon_type='bow'),  # ALREADY HAS weapon_type
    
    InventoryItem('Wand of Lightning', 'weapon', 'Rare',
                 {'intelligence': 10, 'wisdom': 5},
                 skills=['Lightning Bolt'],
                 price=600,
                 weapon_type='wand'),  # ALREADY HAS weapon_type
    
    # Epic items with powerful skills
    InventoryItem('Ring of Vampirism', 'ring', 'Epic',
                 {'strength': 10, 'vitality': 10, 'will': 5},
                 skills=['Life Drain'],
                 price=1500),
    
    InventoryItem('Amulet of Teleportation', 'necklace', 'Epic',
                 {'agility': 12, 'intelligence': 8},
                 skills=['Blink'],
                 price=1500),
    
    InventoryItem('Shadow Scythe', 'weapon', 'Epic',
                 {'agility': 15, 'strength': 10},
                 skills=['Dark Slash'],
                 price=1500,
                 weapon_type='scythe'),
    
    # Legendary items with ultimate skills
    InventoryItem('Dragon Slayer Axe', 'weapon', 'Legendary',
                 {'strength': 20, 'vitality': 15, 'constitution': 10},
                 skills=['Heal'],
                 price=5000,
                 weapon_type='axe'),
    
    InventoryItem('Archmage Staff', 'weapon', 'Legendary',
                 {'intelligence': 25, 'wisdom': 20, 'will': 15},
                 skills=['Meteor Storm'],
                 price=5000,
                 weapon_type='staff'),
    
    InventoryItem('Ring of Time', 'ring', 'Legendary',
                 {'agility': 20, 'intelligence': 15, 'wisdom': 10},
                 skills=['Time Warp'],
                 price=5000),
])
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
        self.x = clamp(self.x, self.size, WINDOW_W - self.size)
        self.y = clamp(self.y, self.size, WINDOW_H - self.size)
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
        self.item = None  # weapon/item
        self.assign_weapon()
    def assign_weapon(self):
        """Assign appropriate weapon based on enemy name"""
        if self.name == "Swordman":
            self.item = Item(self.x, self.y, 'sword', 'silver', 20, owner=self)
        elif self.name == "Spearman":
            self.item = Item(self.x, self.y, 'spear', 'brown', 25, owner=self)
        elif self.name == "Archer":
            self.item = Item(self.x, self.y, 'bow', 'brown', 18, owner=self)
        elif self.name == "Dark Mage":
            self.item = Item(self.x, self.y, 'staff', 'purple', 22, owner=self)
            self.item.gem_color = 'purple'
        elif self.name == "Flame Elemental":
            self.item = Item(self.x, self.y, 'staff', 'orange', 22, owner=self)
            self.item.gem_color = 'orange'
        elif self.name == "Summoner":
            self.item = Item(self.x, self.y, 'staff', 'pink', 22, owner=self)
            self.item.gem_color = 'pink'
        elif self.name == "Healer":
            self.item = Item(self.x, self.y, 'staff', 'yellow', 22, owner=self)
            self.item.gem_color = 'yellow'
        elif self.name == "Ice Golem":
            self.item = Item(self.x, self.y, 'hand', 'cyan', 20, owner=self)
        elif self.name == "Fire Imp":
            self.item = Item(self.x, self.y, 'hand', 'orange', 15, owner=self)
        elif self.name == "Venom Lurker":
            self.item = Item(self.x, self.y, 'hand', 'lime', 18, owner=self)
        elif self.name == "Troll":
            self.item = Item(self.x, self.y, 'hand', 'darkgray', 25, owner=self)
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
        scale_factor = 1 + player_level * 0.5
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
        if self.item:
            self.item.update(self.x, self.y, player.x, player.y)
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
        # Clamp enemy inside its current room boundaries
        # --- Clamp enemy inside current room boundaries ---
        self.x = clamp(self.x, self.size, WINDOW_W - self.size)
        self.y = clamp(self.y, self.size, WINDOW_H - self.size)
        
        # Update room position tracking
        self.room_row = int(self.y // ROOM_H)
        self.room_col = int(self.x // ROOM_W)




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
    shield_radius = 40 + caster.atk
    duration = 3.0
    tick_ms = 100
    shield_id = id(caster)  # Unique ID for this shield

    def shield_tick():
        # Stop if caster is dead or not in room anymore
        if caster not in game.room.enemies:
            return
        
        # Expire if duration passed
        if time.time() >= caster._shield_end:
            caster._shield_active = False
            return

        # Spawn shield particle
        shield_particle = Particle(
            caster.x, caster.y,
            shield_radius,
            "blue",
            life=0.2,
            rtype="shield",
            outline=True
        )
        game.particles.append(shield_particle)

        # Block projectiles
        for proj in list(game.projectiles):
            d = distance((caster.x, caster.y), (proj.x, proj.y))
            if d <= shield_radius + getattr(proj, "radius", 5):
                if proj in game.projectiles:
                    game.projectiles.remove(proj)

        # Reschedule tick
        game.after(tick_ms, shield_tick)

    # Activate shield
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
    arc_radius = 50
    num_particles = 50
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
    offset = arc_radius // 1
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

    offset = arc_radius // 2
    origin_x = px + math.cos(angle_center) * offset
    origin_y = py + math.sin(angle_center) * offset

    # Visual blade only (no per-frame damage)
    blade_particle = Particle(
        origin_x, origin_y,
        arc_radius, 'grey',
        life=0.3,
        rtype='eblade',
        angle=angle_center,
        damage=0
    )
    game.particles.append(blade_particle)

    # Precise sector hit test (radius + player size, angle wedge)
    dx = game.player.x - origin_x
    dy = game.player.y - origin_y
    dist = math.hypot(dx, dy)
    if dist <= arc_radius + game.player.size:
        angle_to_player = math.atan2(dy, dx)
        diff = (angle_to_player - angle_center + 2 * math.pi) % (2 * math.pi)
        if diff <= arc_width / 2 or diff >= 2 * math.pi - arc_width / 2:
            game.damage_player(enemy.atk * 3)

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
                "Swordman", 60, 5, 4, x, y, role="melee",
                skills=[
                    {"skill": enemy_dark_slash, "name": "Arc Slash", "tags": ["melee"], "cooldown": 0.5, "last_used": 0},
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
                "Fire Imp", 60, 8, 4.0, x, y, role="melee",
                skills=[
                    {"skill": fire_slash, "name": "Fire Slash", "tags": ["melee"], "cooldown": 1.0, "last_used": 0},
                    {"skill": self_heal, "name": "Self Heal", "tags": ["magic"], "cooldown": 1.5, "last_used": 0}
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
                    {"skill": ice_blast, "name": "Ice Blast", "tags": ["melee"], "cooldown": 0.5, "last_used": 0},
                    {"skill": self_heal, "name": "Self Heal", "tags": ["magic"], "cooldown": 1.5, "last_used": 0}
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
                    {"skill": life_bolt, "name": "Life Bolt", "tags": ["support"], "cooldown": 0.7, "last_used": 0},
                    {"skill": self_heal, "name": "Self Heal", "tags": ["support"], "cooldown": 1, "last_used": 0}
                ]
            ),
            lambda x, y: Enemy(
                "Venom Lurker", 30, 10, 4.0, x, y, role="melee",
                skills=[
                    {"skill": poison_cloud, "name": "Poison Cloud", "tags": ["melee"], "cooldown": 0.3, "last_used": 0},
                    {"skill": dash_attack, "name": "Dash Attack", "tags": ["support"], "cooldown": 2.0, "last_used": 0},
                    {"skill": self_heal, "name": "Self Heal", "tags": ["magic"], "cooldown": 1.5, "last_used": 0}
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
        self.x = clamp(self.x, self.size, WINDOW_W - self.size)
        self.y = clamp(self.y, self.size, WINDOW_H - self.size)
        
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
import tkinter.messagebox as mb

class SpawnPoint:
    def __init__(self, x, y, radius=70):
        self.x = x
        self.y = y
        self.radius = radius
        self.is_active = False   # Track if this is the active spawn point
        self.protection_end_time = 0  # When protection expires
        self.player_was_inside = False  # Track if player was inside last frame

    def draw(self, canvas):
        # Blue if active, red if not
        color = "blue" if self.is_active else "red"
        
        canvas.create_oval(
            self.x - self.radius, self.y - self.radius,
            self.x + self.radius, self.y + self.radius,
            outline=color,width=3
        )
        canvas.create_oval(
            self.x - self.radius - 5, self.y - self.radius - 5,
            self.x + self.radius + 5, self.y + self.radius + 5,
            outline="white", width=2
        )

    def update(self, game):
        current_time = time.time()
        is_protected = current_time < self.protection_end_time
        
        # Block projectiles only during protection
        if is_protected:
            for proj in list(game.projectiles):
                if distance((proj.x, proj.y), (self.x, self.y)) < self.radius:
                    if proj in game.projectiles:
                        game.projectiles.remove(proj)

            # Push enemies back only during protection
            for e in list(game.room.enemies):
                if distance((e.x, e.y), (self.x, self.y)) < self.radius + e.size:
                    ang = math.atan2(e.y - self.y, e.x - self.x)
                    push_dist = self.radius + e.size + 5
                    e.x = self.x + math.cos(ang) * push_dist
                    e.y = self.y + math.sin(ang) * push_dist
                    e.x = clamp(e.x, e.size, WINDOW_W - e.size)
                    e.y = clamp(e.y, e.size, WINDOW_H - e.size)

        # Check if player is inside
        p = game.player
        player_inside = distance((p.x, p.y), (self.x, self.y)) < self.radius
        
        # Only set spawn when player enters (wasn't inside before, but is now)
        if player_inside and not self.player_was_inside:
            # Deactivate all other spawn points first
            for room_key, room in game.dungeon.items():
                if room.spawn_point:
                    room.spawn_point.is_active = False
            
            # Set this as active spawn
            self.is_active = True
            game.player_spawn_row = game.room_row
            game.player_spawn_col = game.room_col
            game.player_spawn_x = self.x
            game.player_spawn_y = self.y
            print(f"Spawn point set at room ({game.room_row}, {game.room_col})!")
        
        # Update tracking
        self.player_was_inside = player_inside
# ---------- Room ----------
class Room:
    def __init__(self, row, col, dungeon_id=1, player_level=1):
        self.row = row
        self.col = col
        self.enemies = []
        
        # Don't spawn a spawn point in starting room or boss room
        if (row == 0 and col == 4):
            self.spawn_point = None
        else:
            self.spawn_point = SpawnPoint(WINDOW_W//2, WINDOW_H//2)
        
        # Starting room has no enemies
        if (row, col) == (0, 0):
            return
        
        depth = row + col
        # Spawn enemies scaled to player level
        spawn_enemies_for_dungeon(self, dungeon_id, player_level, count=4 + depth)
        
        # Spawn boss in boss room
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
        self.canvas = tk.Canvas(self, width=WINDOW_W, height=WINDOW_H, bg="black")
        self.canvas.pack(fill='both', expand=True)
        self.keys = {}
        self.room_row=0; self.room_col=0
        self.dungeon={}
        self.room=self.get_room(0,0)
        self.projectiles=[]; self.particles=[]
        self.mouse_pos=(WINDOW_W//2,WINDOW_H//2)
        self.show_stats=False
        self.dead=False; self.respawn_time=0; self.respawn_delay=5
        self.bind("o", lambda e: self.open_skill_page())
        self.bind("r", lambda e: game.rotate_beam(-2))  # rotate left
        self.bind("t", lambda e: game.rotate_beam(2))
        self.bind("i", lambda e: self.open_inventory())# rotate right
        self.bind_all('<KeyPress>', self.on_key_down)
        self.bind_all('<KeyRelease>', self.on_key_up)
        self.canvas.bind('<Button-1>', self.handle_stat_click)
        self.player = player
        self.summons = []
        self.player_spawn_row = 0
        self.player_spawn_col = 0
        self.player_spawn_x = WINDOW_W // 2
        self.player_spawn_y = WINDOW_H // 2
        self.player_beam = None  # player's beam
        self.beam_rotation_speed = 0.05  # radians per frame


        self.last_time=time.time()
        self.after(16,self.loop)
    # In GameFrame.__init__(), add:

# Add this method to GameFrame:
    def open_inventory(self):
        """Open inventory window"""
        inv_win = tk.Toplevel(self)
        inv_win.title("Inventory")
        inv_win.geometry("600x500")
        inv_win.configure(bg="#1a1a1a")
        
        # Coins display at the top
        coin_frame = tk.Frame(inv_win, bg="#2a2a2a")
        coin_frame.pack(fill='x', pady=10, padx=10)
        tk.Label(coin_frame, text=f"💰 Coins: {self.player.coins}", 
                font=("Arial", 16, "bold"), bg="#2a2a2a", fg="gold").pack()
        
        # Create scrollable frame
        canvas = tk.Canvas(inv_win, bg="#1a1a1a", highlightthickness=0)
        scrollbar = ttk.Scrollbar(inv_win, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#1a1a1a")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        # Display items
        if not self.player.inventory:
            tk.Label(scrollable_frame, text="Inventory is empty", 
                    font=("Arial", 14), bg="#1a1a1a", fg="gray").pack(pady=20)
        else:
            for item in self.player.inventory:
                item_frame = tk.Frame(scrollable_frame, bg="#2a2a2a", bd=2, relief="groove")
                item_frame.pack(fill='x', pady=5, padx=5)
                
                # Item name with rarity color
                name_text = item.name
                if item.soulbound:
                    name_text += " ⭐"  # Star indicator for soulbound
                name_label = tk.Label(item_frame, text=name_text, 
                                     font=("Arial", 14, "bold"),
                                     bg="#2a2a2a", fg=item.get_color())
                name_label.pack(anchor='w', padx=10, pady=5)
                
                # Item description
                desc_text = item.get_description()
                if item.soulbound:
                    desc_text += "\n[Soulbound: Stats apply even when unequipped]"
                desc_label = tk.Label(item_frame, text=desc_text,
                                     font=("Arial", 10), bg="#2a2a2a", fg="white",
                                     justify='left')
                desc_label.pack(anchor='w', padx=10, pady=2)
                
                # Button container
                button_frame = tk.Frame(item_frame, bg="#2a2a2a")
                button_frame.pack(side='right', padx=10, pady=5)
                
                # Equip/Unequip button (for ALL items including soulbound)
                is_equipped = item in self.player.equipped_items
                btn_text = "Unequip" if is_equipped else "Equip"
                btn_color = "#c9302c" if is_equipped else "#5cb85c"

                def make_equip_callback(itm):
                    def callback():
                        if itm in self.player.equipped_items:
                            self.player.unequip_item(itm)
                        else:
                            self.player.equip_item(itm)
                        inv_win.destroy()
                        self.open_inventory()
                    return callback

                equip_btn = tk.Button(button_frame, text=btn_text, bg=btn_color,
                                     fg="white", font=("Arial", 10, "bold"),
                                     command=make_equip_callback(item))
                equip_btn.pack(side='left', padx=5)

                # Sell button (only for non-soulbound items)
                if not item.soulbound:
                    sell_price = max(1, item.price // 2)
                    
                    def make_sell_callback(itm, price):
                        def callback():
                            self.player.coins += price
                            self.player.remove_item_from_inventory(itm)
                            inv_win.destroy()
                            self.open_inventory()
                        return callback
                    
                    sell_btn = tk.Button(button_frame, text=f"Sell ({sell_price}💰)",
                                        bg="#f0ad4e", fg="white",
                                        font=("Arial", 10, "bold"),
                                        command=make_sell_callback(item, sell_price))
                    sell_btn.pack(side='left', padx=5)
    def rotate_beam(self, delta_angle):
        if hasattr(self, "player_beam") and self.player_beam:
            self.player_beam.rotate(delta_angle)
    def open_skill_page(self):
        # Create a new window
        win = tk.Toplevel(self)
        win.title("Skill Management")
        win.geometry("700x600")
        win.configure(bg="#1a1a1a")  # dark background

        # --- Top: Active skills ---
        active_box = tk.Frame(win, bg="#2a2a2a", bd=0, relief="flat")
        active_box.pack(pady=10, padx=15, fill="x")

        tk.Label(active_box, text="Active Skills (Keybinds)",
                 font=("Arial", 14, "bold"),
                 bg="#2a2a2a", fg="#b0b0b0").pack(pady=5)

        self.active_frame = tk.Frame(active_box, bg="#2a2a2a")
        self.active_frame.pack(pady=5, fill="x")
        self.refresh_active_skills()

        # --- Divider line ---
        divider = tk.Frame(win, bg="#333333", height=2)
        divider.pack(fill="x", pady=10)

        # --- Bottom: Unlocked skills with scroll ---
        unlocked_box = tk.Frame(win, bg="#2a2a2a", bd=0, relief="flat")
        unlocked_box.pack(pady=10, padx=15, fill="both", expand=True)

        tk.Label(unlocked_box, text="Unlocked Skills",
                 font=("Arial", 14, "bold"),
                 bg="#2a2a2a", fg="#b0b0b0").pack(pady=5)

        # Scrollable Canvas
        canvas = tk.Canvas(unlocked_box, bg="#2a2a2a", highlightthickness=0)
        scrollbar = tk.Scrollbar(unlocked_box, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#2a2a2a")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Grid for unlocked skills inside scrollable frame
        for i, sk in enumerate(self.player.unlocked_skills):
            row = tk.Frame(scrollable_frame, bg="#3a3a3a", padx=10, pady=10)
            row.grid(row=i//2, column=i%2, padx=10, pady=10, sticky="nsew")

            # Skill name
            name_label = tk.Label(row, text=sk['name'],
                                  anchor="center", font=("Arial", 11, "bold"),
                                  bg="#3a3a3a", fg="#b0b0b0")
            name_label.pack(fill="x", pady=(0, 5))

            # Slot buttons
            btn_frame = tk.Frame(row, bg="#3a3a3a")
            btn_frame.pack()
            for slot in range(1, 6):
                b = tk.Button(btn_frame, text=str(slot),
                              width=3,
                              font=("Arial", 10, "bold"),
                              bg="#4a4a4a", fg="#b0b0b0",
                              activebackground="#5a5a5a",
                              activeforeground="#b0b0b0",
                              command=lambda s=slot, skill=sk: self.assign_skill(skill, s))
                b.pack(side="left", padx=2)

        scrollable_frame.grid_columnconfigure(0, weight=1)
        scrollable_frame.grid_columnconfigure(1, weight=1)



    def refresh_active_skills(self):
        # Clear old widgets
        for w in self.active_frame.winfo_children():
            w.destroy()

        # Show slots 1–5 on the Y axis
        for slot in range(1, 6):
            row = tk.Frame(self.active_frame, bg="#2a2a2a", padx=8, pady=5)
            row.pack(fill="x", pady=3)

            # Slot number label on the left
            slot_label = tk.Label(row,
                                  text=str(slot),
                                  font=("Arial", 12, "bold"),
                                  bg="#2a2a2a", fg="#b0b0b0", width=3)
            slot_label.pack(side="left", padx=(0, 10))

            # Find skill assigned to this slot (if any)
            assigned_skill = None
            # in refresh_active_skills
            for sk in self.player.unlocked_skills:
                if sk.get("key") == slot:
                    assigned_skill = sk
                    break


            if assigned_skill:
                # Skill name
                name_label = tk.Label(row,
                                      text=assigned_skill['name'],
                                      font=("Arial", 12, "bold"),
                                      bg="#2a2a2a", fg="#b0b0b0")
                name_label.pack(side="left")

                # Keybind + cooldown info
                info_label = tk.Label(row,
                                      text=f"Key: {assigned_skill['key']} | CD: {assigned_skill['cooldown']}s",
                                      font=("Arial", 11),
                                      bg="#2a2a2a", fg="#808080")
                info_label.pack(side="right")
            else:
                # Empty slot placeholder    
                empty_label = tk.Label(row,
                                       text="Empty",
                                       font=("Arial", 11, "italic"),
                                       bg="#2a2a2a", fg="#555555")
                empty_label.pack(side="left")


    def assign_skill(self, skill, slot):
        """
        Assign a skill to a specific slot (1–5) and update its keybind.
        """
        # First, clear any skill already in this slot
        for sk in self.player.unlocked_skills:
            if sk.get("assigned_slot") == slot:
                sk["assigned_slot"] = None
                sk["key"] = 0  # reset keybind

        # Assign this skill to the chosen slot
        skill["assigned_slot"] = slot
        skill["key"] = slot   # update keybind to match slot number

        # Refresh the active skills display
        self.refresh_active_skills()


    def get_room(self, row, col):
        key = (row, col)
        if key not in self.dungeon:
            self.dungeon[key] = Room(row, col, self.dungeon_id, player_level=self.player.level)
        return self.dungeon[key]

    def on_key_down(self, e):
        self.keys[e.keysym] = True

        if e.keysym.lower() == 'p':
            self.show_stats = not self.show_stats
        if e.keysym.lower() == 'i':
            self.open_inventory()
        if e.keysym == 'Escape':
            self.on_quit_to_menu()
        if e.keysym.lower() == 'o':
            self.open_skill_page()

        # Beam rotation keys
        if e.keysym.lower() == 'r':
            if hasattr(self, "player_beam") and self.player_beam:
                self.player_beam.rotate(-0.05)  # rotate left
        if e.keysym.lower() == 't':
            if hasattr(self, "player_beam") and self.player_beam:
                self.player_beam.rotate(0.05)   # rotate right


    def point_to_line_distance(self, px, py, x1, y1, x2, y2):
        """Calculate distance from point (px, py) to line segment (x1,y1)-(x2,y2)"""
        line_len_sq = (x2 - x1)**2 + (y2 - y1)**2
        if line_len_sq == 0:
            return math.hypot(px - x1, py - y1)
        
        t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / line_len_sq))
        proj_x = x1 + t * (x2 - x1)
        proj_y = y1 + t * (y2 - y1)
        return math.hypot(px - proj_x, py - proj_y)

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

    # In GameFrame.damage_enemy()
    def damage_enemy(self,e,amount):
        e.hp -= amount
        if e.hp <=0 and e in self.room.enemies:
            # Award coins
            coins = int(e.max_hp / 10)
            self.player.coins += coins
            
            # Visual coin notification
            self.canvas.create_text(e.x, e.y - 30, text=f"+{coins} coins",
                                   fill='gold', font=('Arial', 12, 'bold'), tags='coin_text')
            self.canvas.after(1000, lambda: self.canvas.delete('coin_text'))
            
            self.player.gain_xp(e.max_hp*2)
            self.room.enemies.remove(e)
    def update_entities(self,dt):
        self.player.speed = self.player.base_speed
        for e in self.room.enemies:
            e.spd = e.base_spd
        
        # Apply frost debuffs
        for part in self.particles:
            if part.rtype == "frost":
                # Affect enemies if owned by player
                if part.owner == "player":
                    for e in list(self.room.enemies):
                        if distance((e.x, e.y), (part.x, part.y)) <= part.size:
                            e.spd = e.base_spd * 0.1  # 60% slow
                # Affect player if owned by enemy
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
        if self.room.spawn_point:
            self.room.spawn_point.update(self)
        # Update beam
        if hasattr(self, 'player_beam') and self.player_beam:
            self.player_beam.update(dt)
            self.player_beam.update_origin(self.player.x, self.player.y)
            
            # Check if beam duration expired
            if hasattr(self, 'beam_active_until') and time.time() >= self.beam_active_until:
                self.player_beam = None
            
            # Damage enemies
            if self.player_beam and self.player_beam.current_length > 0:
                for e in list(self.room.enemies):
                    beam_end_x = self.player_beam.origin_x + math.cos(self.player_beam.angle) * self.player_beam.current_length
                    beam_end_y = self.player_beam.origin_y + math.sin(self.player_beam.angle) * self.player_beam.current_length
                    
                    dist_to_beam = self.point_to_line_distance(
                        e.x, e.y,
                        self.player_beam.origin_x, self.player_beam.origin_y,
                        beam_end_x, beam_end_y
                    )
                    
                    if dist_to_beam < e.size + self.player_beam.size/2:
                        self.damage_enemy(e, self.player.mag * dt * 5)
        if self.player.hp > 0 and self.player_beam:
            self.player_beam.update(dt)
            self.player_beam.update_origin(self.player.x, self.player.y)
        else:
            self.player_beam = None
            self.beam_active_until = 0

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
    def switch_room(self, new_row, new_col, new_x, new_y):
        self.room_row = new_row
        self.room_col = new_col
        self.player.x, self.player.y = new_x, new_y
        self.room = self.get_room(self.room_row, self.room_col)
        self.particles.clear()
        self.projectiles.clear()
        
        # Reposition summons
        for s in self.summons:
            s.room_row = self.room_row
            s.room_col = self.room_col
            s.x = self.player.x + 20
            s.y = self.player.y + 20

    def update_player(self,dt):
        p=self.player
        p.hp=min(p.max_hp, p.hp+p.hp_regen*dt)
        p.mana=min(p.max_mana, p.mana+p.mana_regen*dt)
        
        if self.dead:
            self.respawn_time -= dt
            if self.respawn_time<=0:
                self.particles.clear()
                self.projectiles.clear()
                p.die()
                p.hp = p.max_hp; p.mana = p.max_mana
                self.dead=False
                if hasattr(self, "player_beam"):
                    self.player_beam = None
                    self.beam_active_until = 0
                
                # Respawn at saved spawn point
                self.room_row = self.player_spawn_row
                self.room_col = self.player_spawn_col
                self.room = self.get_room(self.room_row, self.room_col)
                p.x = self.player_spawn_x
                p.y = self.player_spawn_y
                self.room.spawn_point.protection_end_time = time.time() + 2.0
                print(f"Respawned at room ({self.room_row}, {self.room_col})!")
            return
        
        # Store position before movement
        old_x, old_y = p.x, p.y
        
        # movement
        if self.keys.get('Up'):
            p.y -= p.speed
        if self.keys.get('Down'):
            p.y += p.speed
        if self.keys.get('Left'):
            p.x -= p.speed
        if self.keys.get('Right'):
            p.x += p.speed
        
        # Check if player actually moved (pressed a key)
        player_moved = (p.x != old_x or p.y != old_y)
        
        # Room transitions - only trigger if player is actively moving
        margin = 10
        
        if player_moved:
            if p.x < 0 and self.room_col > 0:
                self.switch_room(self.room_row, self.room_col - 1, WINDOW_W - margin, p.y)
                return  # Skip clamping this frame since we switched rooms
            elif p.x > WINDOW_W and self.room_col < ROOM_COLS - 1:
                self.switch_room(self.room_row, self.room_col + 1, margin, p.y)
                return
            elif p.y < 0 and self.room_row > 0:
                self.switch_room(self.room_row - 1, self.room_col, p.x, WINDOW_H - margin)
                return
            elif p.y > WINDOW_H and self.room_row < ROOM_ROWS - 1:
                self.switch_room(self.room_row + 1, self.room_col, p.x, margin)
                return
        
        # Clamp inside current room (only if we didn't switch rooms)
        p.x = clamp(p.x, 0, WINDOW_W)
        p.y = clamp(p.y, 0, WINDOW_H)

        # skills usage (rest of your code continues here...)
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
                    sk['cooldown_mod']=max(0.2, mod*0.9995)

    def handle_stat_click(self, event):
        if not self.show_stats or self.player.stat_points <= 0:
            return
        
        mx, my = event.x, event.y
        stat_y_start = 120
        stat_height = 40  # matches the new spacing in draw_stats_panel
        stats = ['strength','vitality','agility','constitution','intelligence','wisdom','will']
        
        for i, stat in enumerate(stats):
            btn_x = 600
            btn_y = stat_y_start + i * stat_height
            btn_w, btn_h = 30, 30  # matches the new black box size
            
            if btn_x < mx < btn_x + btn_w and btn_y < my < btn_y + btn_h:
                setattr(self.player, stat, getattr(self.player, stat) + 1)
                self.player.stat_points -= 1
                self.player.update_stats()
                break  # stop after one click is processed

    def draw(self):
        self.canvas.delete('all')
        px, py = self.player.x, self.player.y

        # Find equipped weapon and create visual
        equipped_weapon = None
        weapon_item = None

        for item in self.player.equipped_items:
            if item.item_type == 'weapon':
                equipped_weapon = item
                break

        # Create weapon visual from equipped weapon
        # Create weapon visual from equipped weapon
        if equipped_weapon:
            # Get weapon_type, default to 'sword' if missing
            weapon_visual = getattr(equipped_weapon, 'weapon_type', None)
            
            if not weapon_visual:
                print(f"WARNING: {equipped_weapon.name} has no weapon_type! Defaulting to sword")
                weapon_visual = 'sword'
            
            # Create Item object for drawing
            weapon_item = Item(px, py, weapon_visual, 'silver', 20, owner=self.player)
            
            # Set special colors for different weapon types
            if weapon_visual == 'staff':
                if self.player.class_name == 'Mage':
                    weapon_item.color = 'blue'
                    weapon_item.gem_color = 'cyan'
                elif self.player.class_name == 'Cleric':
                    weapon_item.color = 'gold'
                    weapon_item.gem_color = 'yellow'
                elif self.player.class_name == 'Druid':
                    weapon_item.color = 'green'
                    weapon_item.gem_color = 'lime'
            elif weapon_visual == 'wand':
                weapon_item.color = 'purple'
                weapon_item.gem_color = 'yellow'
            elif weapon_visual == 'dagger':
                weapon_item.color = 'purple'
            elif weapon_visual == 'hand':
                weapon_item.color = '#FFA500'
            elif weapon_visual == 'bow':
                weapon_item.color = 'brown'
            elif weapon_visual == 'sword':
                weapon_item.color = 'silver'
            elif weapon_visual == 'katana':
                weapon_item.color = 'silver'
            elif weapon_visual == 'axe':
                weapon_item.color = 'silver'
            elif weapon_visual == 'scythe':
                weapon_item.color = 'gray'
            elif weapon_visual == 'quarterstaff':
                weapon_item.color = 'brown'
                    
            # Update weapon position to aim at nearest enemy
            if self.room.enemies:
                target = min(self.room.enemies, key=lambda e: distance((px, py), (e.x, e.y)))
                weapon_item.update(px, py, target.x, target.y)
            else:
                weapon_item.update(px, py, px + 50, py)

            # Draw weapons that go UNDER the player body
            if weapon_visual in ("spear", "staff", "sword", "dagger", "quarterstaff", "katana", "axe", "scythe"):
                weapon_item.draw(self.canvas)

        # Draw player body
        CLASS_COLORS = {
            "Warrior": "red",
            "Mage": "blue",
            "Rogue": "purple",
            "Cleric": "yellow",
            "Druid": "green",
            "Monk": "orange",
            "Ranger": "brown",
        }

        size = 12
        player_color = CLASS_COLORS.get(self.player.class_name, "cyan")

        # White outline
        self.canvas.create_oval(px-size-2, py-size-2, px+size+2, py+size+2, fill='white')
        # Colored body
        self.canvas.create_oval(px-size, py-size, px+size, py+size, fill=player_color)

        # First character of player name (uppercase)
        initial = self.player.name[0].upper()
        self.canvas.create_text(px, py, text=initial, fill='black', font=('Helvetica', 10, 'bold'))

        # Draw weapons that go ON TOP of player body (like bow)
        if weapon_item and equipped_weapon and hasattr(equipped_weapon, 'weapon_type'):
            if equipped_weapon.weapon_type not in ("spear", "staff", "sword", "dagger", "quarterstaff", "katana", "axe", "scythe"):
                weapon_item.draw(self.canvas)

# Continue with summons drawing...
        for s in self.summons:
            s.draw(self.canvas)
        if self.room.spawn_point:
            self.room.spawn_point.draw(self.canvas)
        for e in self.room.enemies:
            ex, ey = e.x, e.y

            # Decide layering rules
            weapons_below = ("spear", "staff", "hand","sword")   # drawn BEFORE body
            weapons_above = ("bow")                      # drawn AFTER body

            # Bosses: draw their special body first
            if isinstance(e, Boss):
                boss_shapes = {
                    "FireLord": ("rectangle", "orange"),
                    "IceGiant": ("diamond", "cyan"),
                    "ShadowWraith": ("triangle", "purple"),
                    "EarthTitan": ("oval", "brown"),
                }
                outline_width = 3
                outline_color = "white"
                shape, color = boss_shapes.get(e.boss_type, ("oval", "orange"))
                size = e.size

                # Body first
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

                # Boss health name is drawn after the loop elsewhere
                # Draw bow AFTER body if boss has one
                if e.item and e.item.item_type in weapons_above:
                    e.item.draw(self.canvas)
                elif e.item and e.item.item_type in weapons_below:
                    # If you ever want some boss weapons beneath, draw them before body (move above body block)
                    pass
                # Skip normal enemy body code
                continue

            # ---------- Normal enemies ----------
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

            # 1) Draw weapons that should be beneath the body
            if e.item and e.item.item_type in weapons_below:
                e.item.draw(self.canvas)

            # 2) Draw the enemy body
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

            # Health text
            health_text = f"{int(e.hp)}/{int(e.max_hp)}"
            self.canvas.create_text(ex, ey - e.size - 10, text=health_text, fill='white')

            # 3) Draw weapons that should sit on top of the body (bow)
            if e.item and e.item.item_type in weapons_above:
                e.item.draw(self.canvas)

            
        boss_in_room = None
        for e in self.room.enemies:
            if isinstance(e, Boss):
                boss_in_room = e
                break
        # Draw player beam if active
        if self.player_beam:
            self.player_beam.draw(self.canvas)
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
            if part.rtype == "aura":
                self.canvas.create_oval(
                    part.x - part.size, part.y - part.size,
                    part.x + part.size, part.y + part.size,
                    fill=part.color,                # no fill, just outline
                    outline=part.color,     # outline in particle color
                    width=2                 # thickness of the outline
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
        # --- HP bar ---
        self.canvas.create_rectangle(10, 10, 210, 30, fill='gray')
        hpw = int((self.player.hp / self.player.max_hp) * 200) if self.player.max_hp else 0
        self.canvas.create_rectangle(10, 10, 10 + hpw, 30, fill='red')

        # Show HP numbers as integers
        hp_text = f"{int(self.player.hp)}/{int(self.player.max_hp)}"
        self.canvas.create_text(110, 20, text=hp_text, fill='white', font=('Agency FB', 10, 'bold'))

        # --- Mana bar ---
        self.canvas.create_rectangle(10, 35, 210, 55, fill='gray')
        mw = int((self.player.mana / self.player.max_mana) * 200) if self.player.max_mana else 0
        self.canvas.create_rectangle(10, 35, 10 + mw, 55, fill='blue')

        # Show Mana numbers as integers
        mana_text = f"{int(self.player.mana)}/{int(self.player.max_mana)}"
        self.canvas.create_text(110, 45, text=mana_text, fill='white', font=('Agency FB', 10, 'bold'))

        self.canvas.create_rectangle(10,60,210,70,fill='gray')
        xpw=int((self.player.xp/self.player.xp_to_next)*200) if self.player.xp_to_next else 0
        self.canvas.create_rectangle(10,60,10+xpw,70,fill='green')
        self.canvas.create_text(220,60,text=f'LV {self.player.level}',fill='white',anchor='nw')

        # In GameFrame.draw(), replace the skill icons section with:

        # Skills icons + cooldown overlay
        CLASS_COLORS = {
            "Warrior": "red",
            "Mage": "blue",
            "Rogue": "purple",
            "Cleric": "gold",
            "Druid": "green",
            "Monk": "orange",
            "Ranger": "brown",
        }

        now = time.time()
        for slot in range(1, 6):
            sk = next((s for s in self.player.unlocked_skills if s.get("key") == slot), None)
            
            i = slot - 1
            x0 = 10 + i * 60
            y0 = 80
            size = 50

            # pick colour based on player class
            slot_color = CLASS_COLORS.get(self.player.class_name, "grey")

            # draw slot box
            self.canvas.create_rectangle(x0, y0, x0 + size, y0 + size, fill=slot_color)

            # Only draw skill info if skill is assigned to this slot
            if sk:
                # cooldown overlay
                base_cd = sk.get("cooldown", 0)
                mod = sk.get("cooldown_mod", 1.0)
                last_used = sk.get("last_used", 0)
                effective_cd = base_cd * mod
                cd_remaining = max(0, effective_cd - (now - last_used))
                if effective_cd > 0 and cd_remaining > 0:
                    frac = clamp(cd_remaining / effective_cd, 0.0, 1.0)
                    overlay_h = int(size * frac)
                    self.canvas.create_rectangle(x0, y0, x0 + size, y0 + overlay_h, fill="grey")

                # skill icon text
                self.canvas.create_text(x0 + size / 2, y0 + size / 2,
                                        text=sk["name"][0], fill="white")
            else:
                # Empty slot - show slot number
                self.canvas.create_text(x0 + size / 2, y0 + size / 2,
                                        text=str(slot), fill="gray", font=('Arial', 12))

        # Inventory button hint
    def draw_stats_panel(self):
        p = self.player
        
        # Outer frame (white border)
        self.canvas.create_rectangle(100, 100, 700, 500, fill='#1a1a1a', outline='white', width=4)
        
        stats = ['strength','vitality','agility','constitution','intelligence','wisdom','will']
        stat_display_names = {
            'strength': 'STRENGTH',
            'vitality': 'VITALITY', 
            'agility': 'AGILITY',
            'constitution': 'CONSTITUTION',
            'intelligence': 'INTELLIGENCE',
            'wisdom': 'WISDOM',
            'will': 'WILL'
        }
        
        y_start = 120
        stat_height = 40
        
        for i, stat in enumerate(stats):
            base_val = getattr(p, stat)
            
            # Calculate equipment bonus
            equip_bonus = 0

            # Equipped items
            for item in p.equipped_items:
                equip_bonus += item.stats.get(stat, 0)

            # Soulbound items (permanent bonuses)
            for item in p.soulbound_items:
                equip_bonus += item.stats.get(stat, 0)

            
            y = y_start + i * stat_height
            
            # Black box for each stat
            self.canvas.create_rectangle(120, y, 580, y + 30, fill='black')
            
            # Show stat with equipment bonus in brackets
            if equip_bonus > 0:
                stat_text = f'{stat_display_names[stat]}: {base_val} (+{equip_bonus})'
            else:
                stat_text = f'{stat_display_names[stat]}: {base_val}'
                
            self.canvas.create_text(130, y + 15, anchor='w',
                                    text=stat_text,
                                    fill="white", font=('Arial', 14))
            
            # Stat point button (black box with white '+')
            if p.stat_points > 0:
                self.canvas.create_rectangle(600, y, 630, y + 30, fill='black')
                self.canvas.create_text(615, y + 15, text='+', fill='white', font=('Arial', 14))
        
        # Stat points available message
        self.canvas.create_text(120, 420,
                                text=f'Stat Points Available: {p.stat_points}',
                                fill='gray', font=('Arial', 14), anchor='w')
    def loop(self):
        now=time.time(); dt=now-self.last_time; self.last_time=now
        self.update_player(dt)
        self.update_entities(dt)
        self.draw()
        if self.show_stats:
            self.draw_stats_panel()
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
        'Rogue': {'emoji': '🗡', 'color': '#7b1fa2', 'desc': 'Swift and deadly striker\nHigh agility and burst damage'},
        'Cleric': {'emoji': '✨', 'color': '#fbc02d', 'desc': 'Holy warrior and healer\nSupport and light magic'},
        'Druid': {'emoji': '🍃', 'color': '#388e3c', 'desc': 'Nature\'s guardian\nSummons and natural magic'},
        'Monk': {'emoji': '👊', 'color': '#ff6f00', 'desc': 'Chi-powered fighter\nUses HP for devastating attacks'},
        'Ranger': {'emoji': '🏹', 'color': '#CD853F', 'desc': 'Expert archer and trapper\nRanged attacks and tactical skills'}
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
        self.geometry("1000x800")
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
    # In MainApp class, ADD THIS METHOD (not inside build_home):
    def open_shop(self):
        """Open shop window"""
        shop_win = tk.Toplevel(self)
        shop_win.title("Shop")
        shop_win.geometry("700x600")
        shop_win.configure(bg="#1a1a1a")
        
        # Coins display
        coin_frame = tk.Frame(shop_win, bg="#2a2a2a")
        coin_frame.pack(fill='x', pady=10, padx=10)
        
        def update_coins():
            for widget in coin_frame.winfo_children():
                widget.destroy()
            tk.Label(coin_frame, text=f"💰 Your Coins: {self.preview_player.coins}", 
                    font=("Arial", 16, "bold"), bg="#2a2a2a", fg="gold").pack()
        
        update_coins()
        
        # Scrollable shop items
        canvas = tk.Canvas(shop_win, bg="#1a1a1a", highlightthickness=0)
        scrollbar = ttk.Scrollbar(shop_win, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#1a1a1a")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        # Display shop items by rarity
        for rarity in ['Common', 'Uncommon', 'Rare', 'Epic', 'Legendary']:
            rarity_items = [item for item in SHOP_ITEMS if item.rarity == rarity]
            if not rarity_items:
                continue
            
            # Rarity header
            rarity_label = tk.Label(scrollable_frame, text=f"━━━ {rarity} ━━━",
                                   font=("Arial", 14, "bold"),
                                   bg="#1a1a1a", fg=InventoryItem.RARITY_COLORS[rarity])
            rarity_label.pack(pady=(15, 5))
            
            for item in rarity_items:
                item_frame = tk.Frame(scrollable_frame, bg="#2a2a2a", bd=2, relief="groove")
                item_frame.pack(fill='x', pady=5, padx=10)
                
                # Item info
                info_frame = tk.Frame(item_frame, bg="#2a2a2a")
                info_frame.pack(side='left', fill='both', expand=True, padx=10, pady=10)
                
                name_label = tk.Label(info_frame, text=item.name,
                                     font=("Arial", 13, "bold"),
                                     bg="#2a2a2a", fg=item.get_color())
                name_label.pack(anchor='w')
                
                desc_label = tk.Label(info_frame, text=item.get_description(),
                                     font=("Arial", 10), bg="#2a2a2a", fg="white",
                                     justify='left')
                desc_label.pack(anchor='w', pady=2)
                
                # Buy button
                def make_buy_callback(shop_item):
                    def callback():
                        if self.preview_player.coins >= shop_item.price:
                            self.preview_player.coins -= shop_item.price
                            # Create new item instance (not soulbound)
                            new_item = InventoryItem(
                                name=shop_item.name,
                                item_type=shop_item.item_type,
                                rarity=shop_item.rarity,
                                stats=shop_item.stats.copy(),
                                skills=shop_item.skills.copy(),
                                soulbound=False,
                                price=shop_item.price,
                                weapon_type=getattr(shop_item, 'weapon_type', None)  # ADD THIS LINE
                            )
                            self.preview_player.add_item_to_inventory(new_item)
                            update_coins()
                            self.save_player(self.preview_player.to_dict())
                        else:
                            import tkinter.messagebox as mb
                            mb.showwarning("Not Enough Coins", 
                                          f"You need {shop_item.price} coins but only have {self.preview_player.coins}")
                    return callback
                
                buy_btn = tk.Button(item_frame, text=f"Buy\n{item.price} 💰",
                                   bg='#5cb85c', fg='white',
                                   font=("Arial", 11, "bold"),
                                   command=make_buy_callback(item),
                                   width=8)
                buy_btn.pack(side='right', padx=10, pady=10)
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
        # Class selection area
        if not self.class_chosen:
            class_label = tk.Label(self.home_frame, text="Choose Your Class", 
                                  font=("Arial", 20, "bold"), bg='#1a1a1a', fg='#ffffff')
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
        # In MainApp.build_home(), add shop section before dungeon selection:

        # Shop section
        # In MainApp.build_home(), replace the shop section with just:

        # Shop section
        shop_label = tk.Label(self.home_frame, text="🛒 Shop", 
                             font=("Arial", 18, "bold"), bg='#1a1a1a', fg='#ffd700')
        shop_label.pack(pady=(10, 5))

        shop_btn = tk.Button(self.home_frame, text="Open Shop", font=("Arial", 14, "bold"),
                            bg='#5bc0de', fg='white', activebackground='#46b8da',
                            command=self.open_shop, bd=0, padx=20, pady=10, cursor='hand2')
        shop_btn.pack(pady=5)

        # Remove the nested "def open_shop(self):" that was inside build_home
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

        # Outer frame acts as the colored outline
        outline = tk.Frame(parent, bg=info['color'], bd=0)
        outline.pack(side='left', padx=10, pady=10)

        # Inner frame is the button background
        btn_frame = tk.Frame(outline, bg='#2d2d2d', bd=2, relief='solid',
                             width=180, height=120)   # fixed width & height
        btn_frame.pack(padx=2, pady=2)
        btn_frame.pack_propagate(False)  # prevent auto-resizing

        # Emoji + Class name (large font)
        title_label = tk.Label(btn_frame,
                               text=f"{info['emoji']} {class_name}",
                               font=("Arial", 17, "bold"),
                               bg='#2d2d2d', fg=info['color'])
        title_label.pack(pady=(5, 2))

        # Description (smaller font)
        desc_label = tk.Label(btn_frame,
                              text=info['desc'],
                              font=("Arial", 8),
                              bg='#2d2d2d', fg=info['color'],
                              justify='center', wraplength=160)
        desc_label.pack(pady=(0, 5))

        # Make the whole frame clickable
        def on_click(event=None):
            self.choose_class(class_name)

        btn_frame.bind("<Button-1>", on_click)
        title_label.bind("<Button-1>", on_click)
        desc_label.bind("<Button-1>", on_click)


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
        try:
            # Rebuild player from preview
            player = Player.from_dict(self.preview_player.to_dict())
            player.hp = player.max_hp; player.mana = player.max_mana

            # Hide home frame
            self.home_frame.pack_forget()

            # Destroy any existing game frame
            if self.game_frame_container:
                self.game_frame_container.destroy()

            # Resize window to fit game canvas
            self.geometry(f"{int(WINDOW_W + 20)}x{int(WINDOW_H + 40)}")

            # Create and pack the new game frame
            self.game_frame_container = GameFrame(
                self,
                player,
                on_quit_to_menu=self.quit_to_menu,
                dungeon_id=dungeon_id
            )
            self.game_frame_container.pack()

            print(f"Started dungeon {dungeon_id} successfully.")

        except Exception as e:
            print(f"Error starting dungeon {dungeon_id}: {e}")    # ---------- Saving / Loading ----------
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
















