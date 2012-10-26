#########
# imports
#########
import libtcodpy as libtcod
import math
import textwrap
import shelve

###########
# constants
###########
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

MAP_WIDTH = 80
MAP_HEIGHT = 43

ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

MAX_ROOM_MONSTERS = 4

MAX_ROOM_ITEMS = 3

BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT

MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

MAX_ROOM_ITEMS = 3

INVENTORY_WIDTH = 50

HEAL_AMOUNT = 4

MANA_AMOUNT = 3

LIGHTNING_DAMAGE = 20
LIGHTNING_RANGE = 5
LIGHTNING_COST = 4

CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
CONFUSE_COST = 2

FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 12
FIREBALL_COST = 5

STRENGTH_AMOUNT = 4
STRENGTH_NUM_TURNS = 8

DEFENSE_AMOUNT = 3
DEFENSE_NUM_TURNS = 15

BLIZZARD_RADIUS = 4
BLIZZARD_DAMAGE = 18
BLIZZARD_COST = 7

FEAR_NUM_TURNS = 7
FEAR_RANGE = 8
FEAR_COST = 3

AQUABOLT_DAMAGE = 35
AQUABOLT_RANGE = 5
AQUABOLT_COST = 6

#############
# wall colors
#############
color_dark_wall = libtcod.Color(0, 0, 100)
color_light_wall = libtcod.Color(130, 110, 50)
color_dark_ground = libtcod.Color(50, 50, 150)
color_light_ground = libtcod.Color(200, 180, 50)

##################
# game variables
##################
game_state = 'playing'
player_action = None
game_msgs = []
inventory = []
fov_recompute = True

#########
# CLASSES
#########

# tell what each command does and which key to use
class HelpMenu:
    def __init__(self):
        self = self
    
    def move(self):
        return 'Use the arrow keys to move around the screen.'

    def pick_up(self):
        return 'Move over an object and press the \'g\' key to pick it up.'

    def drop(self):
        return 'Press the \'d\' key and then select an item from your inventory to drop it.'

    def inventory(self):
        return 'Press the \'i\' key and then select an item to use it.'

    def combat(self):
        return 'Move into a monster to melee it with your equipped weapon. Select a scroll from your inventory to use it on a monster.'

    def load_save(self):
        return 'Games automatically save when you exit. To load the last played game, press the \'b\' key at the main menu.'

    def levels_exp(self):
        return 'When you kill a monster or complete a quest, you gain experience. When the yellow experience bar fills up, you gain a level! You can view your current level at any time by pressing the \'l\' key.'

    def descending(self):
        return 'When all the monsters on the current floor have been defeated, you will descend to the next floor of the dungeon.'
# rectangle class, used for drawing room
class Rect:
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)

    def intersect(self, other):
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)

# tile class, each square is a tile
class Tile:
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked
        self.explored = False

        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight

# object class, everything placed in rooms are objects
class Object:
    def __init__(self, x, y, char, name, color, blocks=False, fighter=None, ai=None, item=None, level=None, xp=None):
        self.name = name
        self.blocks = blocks
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        if level != None:
            self.level = level
            self.xp = 0
            self.next_lvl = 20

        if xp != None:
            self.xp = xp

        self.fighter = fighter
        if self.fighter:
            self.fighter.owner = self

        self.ai = ai
        if self.ai:
            self.ai.owner = self

        self.item = item
        if self.item:
            self.item.owner = self

    def move(self, dx, dy):
        if not is_blocked(self.x + dx, self.y + dy):
            self.x = self.x + dx
            self.y = self.y + dy

    def draw(self):
        if libtcod.map_is_in_fov(fov_map, self.x, self.y):
            libtcod.console_set_foreground_color(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

    def clear(self):
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

    def move_towards(self, target_x, target_y):
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)

    def move_away(self, target_x, target_y):
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        dx = int(round(dx / distance))
        dy = int(round(dy / distance))

        dx = 0 - dx
        dy = 0 - dy

        self.move()

    def distance_to(self, other):   # distance to another object from the object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def distance(self, x, y):   # distance to coordinates from object
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)
    
    def send_to_back(self):
        global objects
        objects.remove(self)
        objects.insert(0, self)

    def xp_up(self, amount):
        old_xp = self.xp
        self.xp += amount
        if self.xp == self.next_lvl:
            self.level += 1
            self.xp = 0
            message('You have leveled up to level ' + str(self.level) + '!', libtcod.yellow)
            message('Your health and mana have been restored.', libtcod.yellow)
            self.fighter.hp = self.fighter.max_hp
            self.fighter.mana = self.fighter.max_mana
            self.next_lvl = exp_levels[self.level]
            stats_menu('You leveled up! Choose a stat to increase.')

        elif self.xp > self.next_lvl:
            self.xp = (old_xp + amount) - exp_levels[self.level]
            self.level += 1
            message('You have leveled up to level ' + str(self.level) + '!', libtcod.yellow)
            message('Your health and mana have been restored.', libtcod.yellow)
            self.fighter.hp = self.fighter.max_hp
            self.fighter.mana = self.fighter.max_mana
            self.max_xp = exp_levels[self.level]
            self.next_lvl = exp_levels[self.level]
            stats_menu('You leveled up! Choose a stat to increase.')

# fighter class, if something can deal/take damage it is a fighter
class Fighter:
    def __init__(self, hp, defense, power, mana=0, spell_damage=0, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.mana = mana
        self.max_mana = mana
        self.spell_damage = spell_damage
        self.death_function = death_function

    def take_damage(self, damage):
        if self.hp <= 0:
            function = self.death_function
            if function is not None:
               function(self.owner) 
        if damage > 0:
            self.hp -= damage
            if self.hp <= 0:
                function = self.death_function
                if function is not None:
                    function(self.owner)

    def attack(self, target):
        damage = self.power - target.fighter.defense

        if damage > 0:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' damage.')
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but ' + target.name + '\'s defense is too high!')

    def heal(self, amount):
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

# basic monster, will chase/attack player
class BasicMonster:
    def take_turn(self):
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
            if monster.distance_to(player) >= 1.4:
                monster.move_towards(player.x, player.y)

            elif player.fighter.hp > 0:
                monster.fighter.attack(player)

class BossMonster:
    def take_turn(self):
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
            if monster.distance_to(player) >= 1.4 and monster.fighter.hp > 10:
                monster.move_towards(player.x, player.y)
            elif monster.distance_to(player) >= 1.4 and monster.fighter.hp < 10:
                monster.move_away(player.x, player.y)

            elif player.fighter.hp > 0 and monster.fighter.hp > 10:
                monster.fighter.attack(player)
                
# confused monster, will wander around until confusion is over
class ConfusedMonster:
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        if self.num_turns > 0:
            self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
            self.num_turns -=1

        else:
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!')

class FearedMonster:
    def __init__(self, old_ai, num_turns = FEAR_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        if(self.num_turns > 0):
            self.owner.move_away(player.x, player.y)

        else:
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!')
            
# items
class Item:
    def __init__(self, use_function = None):
        self.use_function = use_function
        
    def pick_up(self):
        if len(inventory) >= 26:
            message('You don\'t have enough inventory space to hold ' + self.owner.name + '!')
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '.')

    def use(self):
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() == equip_amulet():
                equipped[0] = self
                inventory.remove(self.owner)
                print('amulet equipped')

            elif self.use_function() == equip_weapon():
                equipped[1] = self
                inventory.remove(self.owner)

            elif self.use_function() == equip_armor():
                equipped[2] = self
                inventory.remove(self.owner)

            elif self.use_function() != 'cancelled':
                inventory.remove(self.owner)
            

    def drop(self):
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.')

######################
# ITEM & SPELL EFFECTS
######################

# Common

def cast_heal():
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', libtcod.light_blue)
        return 'cancelled'

    message('You recover ' + str(HEAL_AMOUNT) + ' health.', libtcod.light_blue)
    player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None:
        message('No enemy is close enough to strike.', libtcod.light_blue)
        return 'cancelled'

    if player.fighter.mana >= LIGHTNING_COST:
        message('A lightning bolt strikes the ' + monster.name + ' for ' + str(LIGHTNING_DAMAGE + player.fighter.spell_damage) + ' damage.', libtcod.light_blue)
        monster.fighter.take_damage(LIGHTNING_DAMAGE + player.fighter.spell_damage)
        
        mana_down(LIGHTNING_COST)

    else:
        message('You don\'t have enough mana to cast lightning bolt!', libtcod.light_blue)

def cast_confuse():
    message('Left click an enemy to confuse it or right click to cancel.', libtcod.light_blue)
    monster = target_monster(CONFUSE_RANGE)
    if monster is None:
        message('Spell cancelled.', libtcod.light_blue)
        return 'cancelled'
    if player.fighter.mana >= CONFUSE_COST:
        old_ai = monster.ai
        monster.ai = ConfusedMonster(old_ai)
        monster.ai.owner = monster
        message('The ' + monster.name + ' is confused!', libtcod.light_blue)
        
        mana_down(CONFUSE_COST)

    else:
        message('You don\'t have enough mana to cast confuse!', libtcod.light_blue)

def cast_fireball():
    message('Left click a tile to cast fireball or right click to cancel.', libtcod.light_blue)
    (x, y) = target_tile()
    if x is None:
        message('Spell cancelled.', libtcod.light_blue)
        return 'cancelled'

    if(player.fighter.mana >= FIREBALL_COST):
        message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!',
                libtcod.light_blue)

        for obj in objects:
            if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
                message('The ' + obj.name + ' is burned and takes ' + str(FIREBALL_DAMAGE + player.fighter.spell_damage) + ' damage.',
                libtcod.light_blue)
                obj.fighter.take_damage(FIREBALL_DAMAGE + player.fighter.spell_damage)

        mana_down(FIREBALL_COST)

    else:
        message('You don\'t have enough mana to cast fireball!', libtcod.light_blue)
        return 'cancelled'

def mana_up():
    if player.fighter.mana == player.fighter.max_mana:
        message('You are already at full mana.', libtcod.light_blue)
        return 'cancelled'

    message('You recover ' + str(MANA_AMOUNT) + ' mana.', libtcod.light_blue)
    player.fighter.mana += MANA_AMOUNT
    if player.fighter.mana > player.fighter.max_mana:
        player.fighter.mana = player.fighter.max_mana

def mana_down(amount):
    if player.fighter.mana == 0:
        message('You don\'t have any mana!')
        return 'cancelled'

    message('You are drained of ' + str(amount) + ' mana.', libtcod.light_blue)
    player.fighter.mana -= amount
    if player.fighter.mana < 0:
        player.fighter.mana = 0

# Uncommon

def strength_up():
    global strength_num_turns

    message('You feel emboldened as your strength increases by ' + str(STRENGTH_AMOUNT) + ' points!', libtcod.light_blue)
    player.fighter.strength += STRENGTH_AMOUNT
    strength_num_turns = STRENGTH_NUM_TURNS

def strength_down():

    player.fighter.strength -= STRENGTH_AMOUNT

def defense_up():
    global defense_num_turns

    message('You feel iron flowing through your veins as your defense increases by ' + str(DEFENSE_AMOUNT) + ' points!', libtcod.light_blue)
    player.fighter.defense += DEFENSE_AMOUNT
    defense_num_turns = DEFENSE_NUM_TURNS

def defense_down():

    player.fighter.defense -= DEFENSE_AMOUNT

def cast_fear():
    message('Left click an enemy to fear it or right click to cancel.', libtcod.light_blue)
    monster = target_monster(FEAR_RANGE)
    if monster is None:
        message('Spell cancelled.', libtcod.light_blue)
        return 'cancelled'
    if player.fighter.mana >= FEAR_COST:
        old_ai = monster.ai
        monster.ai = FearedMonster(old_ai)
        monster.ai.owner = monster
        message('The ' + monster.name + ' flees in fear!', libtcod.light_blue)
        
        mana_down(FEAR_COST)

    else:
        message('You don\'t have enough mana to cast fear!', libtcod.light_blue)
        return 'cancelled'

def cast_blizzard():
    message('Left click a tile to cast blizzard or right click to cancel.', libtcod.light_blue)
    (x, y) = target_tile()
    if x is None:
        message('Spell cancelled.', libtcod.light_blue)
        return 'cancelled'

    if(player.fighter.mana >= BLIZZARD_COST):
        message('A blizzard rains down, dealing ' + str(BLIZZARD_DAMAGE) + ' damage to everything within ' + str(BLIZZARD_RADIUS) + ' tiles!',
                libtcod.light_blue)

        for obj in objects:
            if obj.distance(x, y) <= BLIZZARD_RADIUS and obj.fighter:
                message('The ' + obj.name + ' is hit by blizzard and takes ' + str(BLIZZARD_DAMAGE + player.fighter.spell_damage) + ' damage.',
                libtcod.light_blue)
                obj.fighter.take_damage(BLIZZARD_DAMAGE + player.fighter.spell_damage)

        mana_down(BLIZZARD_COST)

    else:
        message('You don\'t have enough mana to cast blizzard!', libtcod.light_blue)
        return 'cancelled'

def cast_aquabolt():
    monster = closest_monster(AQUABOLT_RANGE)
    if monster is None:
        message('No enemy is close enough to strike.', libtcod.light_blue)
        return 'cancelled'

    if player.fighter.mana >= AQUABOLT_COST:
        message('A bolt of water strikes the ' + monster.name + ' for ' + str(AQUABOLT_DAMAGE + player.fighter.spell_damage) + ' damage.', 
                libtcod.light_blue)
        monster.fighter.take_damage(AQUABOLT_DAMAGE + player.fighter.spell_damage)
        
        mana_down(AQUABOLT_COST)

    else:
        message('You don\'t have enough mana to cast aquabolt!', libtcod.light_blue)

# Rare

def cast_invisibility():
    return

def equip_armor():
    return

def equip_weapon():
    return

def cast_gravity():
    return

# Epic

def equip_halfblades():  # Void Lord's Halfblades
    return

def equip_chainmail(): # Undead Chainmail
    return

def cast_obliterate():
    return

def cast_siphon():
    return

def cast_immobilize():
    return

# Legendary

def equip_amulet():   # Alterlocus
    return

def equip_lash():       # Hackin's Lash, Feathershot
    return

def equip_feathershot():
    return

def cast_argenteus():    # Argenteus
    return

def equip_marrowsplitter():        # Marrowsplitter
    return

################
# KEYBOARD INPUT
################
def handle_keys():
    global fov_recompute
    global dungeon_level

    key = libtcod.console_wait_for_keypress(True)
    if key.vk == libtcod.KEY_ENTER and key.lalt:
       libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'
    if game_state == 'playing':
        if libtcod.console_is_key_pressed(libtcod.KEY_UP):
            player_move_or_attack(0, -1)
        elif libtcod.console_is_key_pressed(libtcod.KEY_DOWN):
            player_move_or_attack(0, 1)
        elif libtcod.console_is_key_pressed(libtcod.KEY_LEFT):
            player_move_or_attack(-1, 0)
        elif libtcod.console_is_key_pressed(libtcod.KEY_RIGHT):
            player_move_or_attack(1, 0)
        else:
            key_char = chr(key.c)
            if key_char == 'g':
                picked_up = False
                for object in objects:
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        picked_up = True
                        break
                if picked_up == False:
                    message('There is nothing to pick up here.')
                    
            elif key_char == 'i':
                chosen_item = inventory_menu('Press the key next to an item to use it.')
                if chosen_item is not None:
                    chosen_item.use()
                    return
                    
            elif key_char == 'd':
                chosen_item = inventory_menu('Press the key next to an item to drop it.')
                if chosen_item is not None:
                    chosen_item.drop()

            elif key_char == 'l':
                message('You are level ' + str(player.level) + '.', libtcod.yellow)
                message('You are on dungeon level ' + str(dungeon_level) + '.', libtcod.yellow)

            elif key_char == 'n':   #debug key
                stats_menu('Cheater.')

            elif key_char == 'a':
                equip_menu('Press the key next to an item to unequip it.')

                    
            return 'didnt-take-turn'

################
# MAP GENERATION
################
def make_map(first_render = False):
    global map, objects, monster_count
    
    if first_render:
        first_render = False
        monster_count = 0

    # put the player in the object list
    objects = [player]

    # creates a map that's the right size as defined by constants
    map = [[ Tile(True)
             for y in range(MAP_HEIGHT) ]
                for x in range(MAP_WIDTH) ]

    # initialize 2D room array
    rooms = []
    num_rooms = 0
    for r in range(MAX_ROOMS):
        
        #random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)

        #random position
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)

        # form new room based on random numbers
        new_room = Rect(x, y, w, h)

        failed = False

        # if the room intersects with another room, it isn't added to map
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        # if it doesn't intersect, create it, place objects in it, and get its center
        if not failed:

            create_room(new_room)
            
            place_objects(new_room)

            (new_x, new_y) = new_room.center()

            # if this is the first room created, place the player at the center
            if(num_rooms == 0):
                player.x = new_x
                player.y = new_y

            # draw tunnels between all rooms
            else:
                (prev_x, prev_y) = rooms[num_rooms - 1].center()

                if(libtcod.random_get_int(0, 0, 1)) == 1:
                   create_h_tunnel(prev_x, new_x, prev_y)
                   create_v_tunnel(prev_y, new_y, new_x)
                else:
                   create_v_tunnel(prev_y, new_y, prev_x)
                   create_h_tunnel(prev_x, new_x, new_y)

            # add room to room array
            rooms.append(new_room)
            num_rooms += 1

# creates a room at a random position
def create_room(room):
    global map
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False

# creates a horizontal 1-tile high tunnel
def create_h_tunnel(x1, x2, y):
    global map
    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

# creates a vertical 1-tile wide tunnel
def create_v_tunnel(y1, y2, x):
    global map
    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

# returns whether or not the coordinates are occupied by something solid
def is_blocked(x, y):
    if map[x][y].blocked:
        return True

    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True

    return False

#####################
# RENDERING & DRAWING
#####################

# renders a bar with a background and foreground color
def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    bar_width = int(float(value) / maximum * total_width)

    libtcod.console_set_background_color(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False)

    libtcod.console_set_background_color(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False)

    libtcod.console_set_foreground_color(panel, libtcod.white)
    libtcod.console_print_center(panel, x+ total_width / 2, y - 1, libtcod.BKGND_NONE,
                                 name + ': ' + str(value) + '/' + str(maximum))
    
# draws everything to the screen
def render_all(first_render = False):
    global fov_map, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute

    if first_render:
        first_render = False
        fov_recompute = True

    if fov_recompute:
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = libtcod.map_is_in_fov(fov_map, x, y)
                wall = map[x][y].block_sight
                if not visible:
                    if map[x][y].explored:
                        if wall:
                            libtcod.console_set_back(con, x, y,
                                                     color_dark_wall, libtcod.BKGND_SET)
                        else:
                            libtcod.console_set_back(con, x, y,
                                                     color_dark_ground, libtcod.BKGND_SET)
                else:
                    if wall:
                        libtcod.console_set_back(con, x, y,
                                                 color_light_wall, libtcod.BKGND_SET)
                    else:
                        libtcod.console_set_back(con, x, y,
                                                 color_light_ground, libtcod.BKGND_SET)
                        map[x][y].explored = True
                        
    for object in objects:
        if object != player:
            object.draw()

    player.draw()
    
    #bottom panel

    libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)

    libtcod.console_set_background_color(panel, libtcod.black)
    libtcod.console_clear(panel)

    y = 1
    for(line, color) in game_msgs:
        libtcod.console_set_foreground_color(panel, color)
        libtcod.console_print_left(panel, MSG_X, y, libtcod.BKGND_NONE, line)
        y+= 1

    render_bar(1, 2, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)
    render_bar(1, 4, BAR_WIDTH, 'MP', player.fighter.mana, player.fighter.max_mana, libtcod.light_sky, libtcod.darker_sky)
    render_bar(1, 6, BAR_WIDTH, 'XP', player.xp, player.next_lvl, libtcod.light_yellow, libtcod.darker_yellow)
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

##################
# SPAWNING OBJECTS
##################

# spawns monsters and items in each room
def place_objects(room):
    global monster_count
    
    # PLACE MONSTERS
    num_monsters = libtcod.random_get_int(0, 0, (MAX_ROOM_MONSTERS + dungeon_level))

    for i in range(num_monsters):
        x = libtcod.random_get_int(0, room.x1, room.x2)
        y = libtcod.random_get_int(0, room.y1, room.y2)

        if not is_blocked(x, y):
            if (libtcod.random_get_int(0, 0, 100)) < (70 - (dungeon_level * 10)):  #80% chance on dungeon level 0
                fighter_component = Fighter(hp=10, defense=0, power=3, death_function = monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'o', 'orc', libtcod.desaturated_green, blocks=True, fighter=fighter_component, ai=ai_component, xp=3)
                
                objects.append(monster)
                monster_count += 1
            
            elif (libtcod.random_get_int(0, 0, 100)) < (80 - (dungeon_level * 7)):
                fighter_component = Fighter(hp=16, defense=1, power=4, death_function = monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'T', 'troll', libtcod.darker_green, blocks=True, fighter=fighter_component, ai=ai_component, xp=5)

                objects.append(monster)
                monster_count += 1

            elif (libtcod.random_get_int(0, 0, 100)) < (90 - (dungeon_level * 5)):
                fighter_component = Fighter(hp=20, defense=2, power=5, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 's', 'skeleton', libtcod.white, blocks=True, fighter=fighter_component, ai=ai_component, xp=20)

                objects.append(monster)
                monster_count += 1

            elif(libtcod.random_get_int(0, 0, 100)) < (100 - (dungeon_level * 3)):
                fighter_component = Fighter(hp=30, defense=5, power=8, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'Z', 'zombie', libtcod.dark_blue, blocks=True, fighter=fighter_component, ai=ai_component, xp=50)

                objects.append(monster)
                monster_count += 1

            if(dungeon_level % 5 == 0) and (dungeon_level != 0):
                fighter_component = Fighter(hp=40, defense=5, power=9, death_function=boss_death)
                ai_component = BossMonster()
                loot_component = Item(use_function = cast_heal)
                bossLoot = Object(x, y, '!', 'healing potion', libtcod.violet, item=loot_component)

                monster = Object(x, y, 'V', 'Void Lord', libtcod.black, blocks=True, fighter=fighter_component, ai=ai_component, xp=100, loot=bossLoot)

                objects.append(monster)
                monster_count += 1
                message('You feel a chill...', libtcod.gray)

    # PLACE ITEMS
    num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)

    for i in range(num_items):
        x = libtcod.random_get_int(0, room.x1, room.x2)
        y = libtcod.random_get_int(0, room.y1, room.y2)

        if not is_blocked(x, y):
            dice = libtcod.random_get_int(0, 0, 100)
            if dice < 50:
                item_component = Item(use_function = cast_heal)
                item = Object(x, y, '!', 'healing potion', libtcod.violet, item=item_component)

                objects.append(item)
                item.send_to_back()

            elif dice < 50 + 20:
                item_component = Item(use_function = mana_up)
                item = Object(x, y, '!', 'mana poition', libtcod.violet, item=item_component)

                objects.append(item)
                item.send_to_back()
                
            elif dice < 70 + 10:
                item_component = Item(use_function = cast_lightning)
                item = Object(x, y, '#', 'scroll of lightning bolt', libtcod.violet, item=item_component)

                objects.append(item)
                item.send_to_back()

            elif dice < 70 + 10 + 10:
                item_component = Item(use_function = cast_fireball)
                item = Object(x, y, '#', 'scroll of fireball', libtcod.violet, item=item_component)     
                
                objects.append(item)
                item.send_to_back()

            else:
                item_component = Item(use_function = cast_confuse)
                item = Object(x, y, '#', 'scroll of confusion', libtcod.violet, item=item_component)

                objects.append(item)
                item.send_to_back()

# Item drops
def choose_random_item(x, y, rarity=0):
    dice = libtcod.random_get_int(0, 0, 100)
    item = None

    if(rarity == 0):
        if(dice > 80):     # 20% chance for each item
            item_component = Item(use_function = cast_heal)
            item = Object(x, y, '!', 'healing potion', libtcod.violet, item=item_component)
        elif(dice > 60):
            item_component = Item(use_function = mana_up)
            item = Object(x, y, '!', 'mana poition', libtcod.violet, item=item_component)
        elif(dice > 40):
            item_component = Item(use_function = cast_lightning)
            item = Object(x, y, '#', 'scroll of lightning bolt', libtcod.violet, item=item_component)
        elif(dice > 20):
            item_component = Item(use_function = cast_fireball)
            item = Object(x, y, '#', 'scroll of fireball', libtcod.violet, item=item_component) 
        else:
            item_component = Item(use_function = cast_confuse)
            item = Object(x, y, '#', 'scroll of confusion', libtcod.violet, item=item_component)

    elif(rarity == 1):
        if(dice > 80):
            item_component = Item(use_function = strength_up)
            item = Object(x, y, '!', 'strength potion', libtcod.violet, item = item_component)
        elif(dice > 60):
            item_component = Item(use_function = defense_up)
            item = Object(x, y, '!', 'defense potion', libtcod.violet, item = item_component)
        elif(dice > 40):
            item_component = Item(use_function = cast_blizzard)
            item = Object(x, y, '#', 'scroll of blizzard', libtcod.violet, item = item_component)
        elif(dice > 20):
            item_component = Item(use_function = cast_fear)
            item = Object(x, y, '#', 'scroll of fear', libtcod.violet, item = item_component)
        else:
            item_component = Item(use_function = cast_aquabolt)
            item = Object(x, y, '#', 'scroll of aquabolt', libtcod.violet, item = item_component)

    elif(rarity == 2):
        if(dice > 80):
            item_component = Item(use_function = equip_weapon)
            item = Object(x, y, ')', 'stocky crossbow', libtcod.white, item = item_component)
        elif(dice > 60):
            item_component = Item(use_function = cast_invisibility)
            item = Object(x, y, '#', 'scroll of invisibility', libtcod.violet, item = item_component)
        elif(dice > 40):
            item_component = Item(use_function = equip_armor)
            item = Object(x, y, '^', 'well-used helmet', libtcod.blue, item = item_component)
        elif(dice > 20):
            item_component = Item(use_function = equip_weapon)
            item = Object(x, y, '|', 'heavy broadsword', libtcod.white, item = item_component)
        else:
            item_component = Item(use_function = cast_gravity)
            item = Object(x, y, '#', 'scroll of gravity', libtcod.violet, item = item_component)

    elif(rarity == 3):
        if(dice > 80):
            item_component = Item(use_function = equip_halfblades)
            item = Object(x, y, '|', 'void lord\'s halfblades', libtcod.white, item = item_component)
        elif(dice > 60):
            item_component = Item(use_function = equip_chainmail)
            item = Object(x, y, '^', 'undead chainmail', libtcod.blue, item = item_component)
        elif(dice > 40):
            item_component = Item(use_function = cast_obliterate)
            item = Object(x, y, '#', 'scroll of obliterate', libtcod.violet, item = item_component)
        elif(dice > 20):
            item_component = Item(use_function = cast_siphon)
            item = Object(x, y, '#', 'scroll of siphoning', libtcod.violet, item = item_component)
        else:
            item_component = Item(use_function = cast_immobilize)
            item = Object(x, y, '#', 'scroll of immobilize', libtcod.violet, item = item_component)

    elif(rarity == 4):
        if(dice > 80):
            item_component = Item(use_function = equip_alterlocus)
            item = Object(x, y, '^', 'alterlocus', libtcod.blue, item = item_component)
        elif(dice > 60):
            item_component = Item(use_function = equip_lash)
            item = Object(x, y, '|', 'hackin\'s lash', libtcod.white, item = item_component)
        elif(dice > 40):
            item_component = Item(use_function = equip_feathershot)
            item = Object(x, y, ')', 'feathershot', libtcod.white, item = item_component)
        elif(dice > 20):
            item_component = Item(use_function = cast_argenteus)
            item = Object(x, y, '!', 'argenteus', libtcod.violet, item = item_component)
        else:
            item_component = Item(use_function = equip_marrowsplitter)
            item = Object(x, y, '|', 'marrowsplitter', libtcod.white, item = item_component)

    objects.append(item)
    return item

########
# COMBAT
########

# attempts to move the player. if the destination is a monster, attacks the monster.
def player_move_or_attack(dx, dy):
    global fov_recompute, strength_num_turns, defense_num_turns

    x = player.x + dx
    y = player.y + dy

    target = None
    for object in objects:
        if object.fighter and object.x == x and object.y == y:
               target = object
               break

    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True
    if(strength_num_turns > 0):
        strength_num_turns -= 1
        if(strength_num_turns == 0):
            message('You feel yourself returning to normal strength.', libtcod.light_blue)
            strength_down()

    if(defense_num_turns > 0):
        defense_num_turns -= 1
        if(defense_num_turns == 0):
            message('You feel your defenses returning to normal.', libtcod.light_blue)
            defense_down()


# what happens when the player dies        
def player_death(player):
    global game_state
    message('You died!', libtcod.red)
    game_state = 'dead'

    player.fighter.hp = 0
    player.char = '%'
    player.color = libtcod.dark_red

# what happens when a monster dies
def monster_death(monster):
    global monster_count
    
    monster.send_to_back()
    monster_count -= 1
    if monster_count == 1:
        message('1 monster remains on this level.', libtcod.light_green)
    elif monster_count > 0:
        message(str(monster_count) + ' monsters remain on this level.', libtcod.light_green)

    message('The ' + monster.name + ' dies, rewarding you ' + str(monster.xp) + ' exp!', libtcod.light_red)

    player.xp_up(monster.xp)
    monster.xp = None

    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    
    dice = libtcod.random_get_int(0, 0, 100)

    if(dice > 98):
        item = choose_random_item(monster.x, monster.y, rarity=0)
        monster = item
    elif(dice > 95):
        item = choose_random_item(monster.x, monster.y, rarity=1)
        monster = item
    elif(dice > 90):
        item = choose_random_item(monster.x, monster.y, rarity=2)
        monster = item
    elif(dice > 80):
        item = choose_random_item(monster.x, monster.y, rarity=3)
        monster = item
        


def boss_death(monster):
    global monster_count

    message('You have slain the mighty ' + monster.name + '! You gained ' + str(monster.xp) + ' xp.', libtcod.light_red)
    message('The monster dropped a ' + monster.loot.name +'.', libtcod.light_red)
    if(inventory.len < 26):
        inventory.append(monster.loot)
        message('It was added to your inventory.', libtcod.light_red)
    else:
        objects.append(monster.loot)
        monster.loot.x = player.x
        monster.loot.y = player.y
        message('Your inventory was full! The ' + monster.loot.name + ' fell to the ground...', libtcod.light_red)

    monster.char = '%'
    monster.color = libtcode.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name

#############
# POPUP BOXES
#############

# prints a message in the desired color to the message area
def message(new_msg, color = libtcod.white):
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        if len(game_msgs) == MSG_HEIGHT:
               del game_msgs[0]

        game_msgs.append( (line, color) )

# displays a message box containing text
def msgbox(text, width=50):
    menu(text, [], width)

# draws a menu with desired header to the middle of the screen
def menu(header, options, width):
    if len(options) > 26:
        raise ValueError('Error: must have 26 or fewer options')

    header_height = libtcod.console_height_left_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    
    if header == '':
        header_height = 0
        
    height = len(options) + header_height

    window = libtcod.console_new(width, height)

    libtcod.console_set_foreground_color(window, libtcod.white)
    libtcod.console_print_left_rect(window, 0, 0, width, height, libtcod.BKGND_NONE, header)

    y = header_height
    letter_index = ord('a')

    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        libtcod.console_print_left(window, 0, y, libtcod.BKGND_NONE, text)
        y += 1
        letter_index += 1

    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/2 - height/2

    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.8)
    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)

    if key.vk == libtcod.KEY_ENTER and key.lalt:
       libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

    index = key.c - ord('a')
    if index >= 0 and index < len(options):
        return index
    return None

#######
# MENUS
#######

# pauses the game and prints the player's inventory
def inventory_menu(header):
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = [item.name for item in inventory]

    index = menu(header, options, INVENTORY_WIDTH)

    if index is None or len(inventory) == 0:
        return None
    return inventory[index].item

# displays and/or changes a player's stats
def stats_menu(header):
    index = None
    
    while index is None:
        index = menu(header, ['Health: ' + str(player.fighter.hp), 'Mana: ' + str(player.fighter.mana), 'Attack: ' + str(player.fighter.power), 'Defense: ' + str(player.fighter.defense), 'Spell damage: ' + str(player.fighter.spell_damage)], 24)

        if index is 0:
            player.fighter.max_hp += 5
            player.fighter.hp = player.fighter.max_hp
        elif index is 1:
            player.fighter.max_mana += 5
            player.fighter.mana = player.fighter.max_mana
        elif index is 2:
            player.fighter.power += 2
        elif index is 3:
            player.fighter.defense += 1
        elif index is 4:
            player.fighter.spell_damage += 1
        else:
            break

def equip_menu(header):
    index = None
    amulet = 'None'
    weapon = 'None'
    armor = 'None'

    if(equipped[0] != None):
        amulet = equipped[0].owner.name

    if(equipped[1] != None):
        weapon = equipped[1].owner.name

    if(equipped[2] != None):
        armor = equipped[2].owner.name
    
    while index is None: 
        index = menu(header, ['Amulet: ' + amulet, 'Weapon: ' + weapon, 'Armor: ' + armor], 48)

        if index is 0:
            inventory.append(equipped[0].owner)
            equipped[0] = None

        elif index is 1:
            inventory.append(equipped[1].owner)
            equipped[1] = None

        elif index is 2:
            inventory.append(equipped[2].owner)
            equipped[2] = None

        else:
            break
            
# pauses the game and prints the main menu or prints title menu
def main_menu():
    img = libtcod.image_load('menu_background1.png')

    while not libtcod.console_is_window_closed():
        # draw background menu image
        libtcod.image_blit_2x(img, 0, 0, 0)

        libtcod.console_set_foreground_color(0, libtcod.light_blue)
        libtcod.console_print_center(0, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 5, libtcod.BKGND_NONE, 'Hackin\'s Lash')
        libtcod.console_print_center(0, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 4, libtcod.BKGND_NONE, 'A game by Liquix')

        # display options
        choice = menu('', ['Play a new game', 'Continue last game', 'Help', 'Quit'], 24)

        if choice == 0:     # start new game
            new_game()
            play_game()

        elif choice == 1:   # load game
            try:
                load_game()
            except:
                msgbox('\n No saved game to load.\n', 24)
                continue
            play_game()

        elif choice == 2:   # help
            help_menu = menu('Press the key next to a command to learn more about it.',
                             ['Move', 'Pick up', 'Drop', 'Inventory', 'Combat', 'Loading & saving', 'Levels & experience', 'Descending', 'Back to main menu'], 24)
            m = HelpMenu()

            if help_menu == 0:
                msgbox('\n' + m.move() + ' \n', 48)

            elif help_menu == 1:
                msgbox('\n' + m.pick_up() + '\n', 48)

            elif help_menu == 2:
                msgbox('\n' + m.drop() + '\n', 48)

            elif help_menu == 3:
                msgbox('\n' + m.inventory() + '\n', 48)

            elif help_menu == 4:
                msgbox('\n' + m.combat() + '\n', 48)
                
            elif help_menu == 5:
                msgbox('\n' + m.load_save() + '\n', 48)

            elif help_menu == 6:
                msgbox('\n' + m.levels_exp() + '\n', 48)

            elif help_menu == 7:
                msgbox('\n' + m.descending() + '\n', 48)

        elif choice == 3:   # quit
            break

##########
# DISTANCE
##########

# finds the closest monster within max_range
def closest_monster(max_range):
    closest_enemy = None
    closest_dist = max_range + 1

    for object in objects:
        if object.fighter and object != player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            dist = player.distance_to(object)
            if dist < closest_dist:
                closest_enemy = object
                closest_dist = dist
                
    return closest_enemy

# gets the tile that is clicked by the mouse
def target_tile(max_range = None):
    while True:
        render_all()
        libtcod.console_flush()
        key = libtcod.console_check_for_keypress()
        mouse = libtcod.mouse_get_status()
        (x, y) = (mouse.cx, mouse.cy)

        if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and
            (max_range is None or player.distance(x, y) <= max_range)):
            return (x, y)
        
        if mouse.rbutton_pressed:
            return (None, None)

# gets the monster that is clicked by the mouse
def target_monster(max_range = None):
    while True:
        (x, y) = target_tile(max_range)
        if x is None:
            return None

        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj

################
# INITIALIZATION
################

# colors
color_dark_wall = libtcod.Color(0, 0, 100)
color_light_wall = libtcod.Color(130, 110, 50)
color_dark_ground = libtcod.Color(50, 50, 150)
color_light_ground = libtcod.Color(200, 180, 50)

# player variables
game_state = 'playing'
player_action = None
fov_recompute = True
dungeon_level = 0
game_msgs = []
inventory = []
equipped = [None, None, None]
exp_levels = [10, 20, 35, 60, 100, 180, 280, 400, 550, 800]
strength_num_turns = 0
defense_num_turns = 0

# consoles, fonts, FPS    
libtcod.console_set_custom_font('lucida10x10_gs_tc.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Hackin\'s Lash', False)
libtcod.sys_set_fps(LIMIT_FPS)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

# initializes the field of vision
def initialize_fov():
    global fov_recompute, fov_map

    # make sure the FoV is recomputed right after it's created
    fov_recomptue = True

    #create FoV map, using randomly generated map from new_game
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

    # purge any discarded graphics from the screen
    libtcod.console_clear(con)

# main game loop, handles everything
def play_game():
    global dungeon_level
    player_action = None

    render_all(first_render = True)

    # while the game window is open, loop executes
    while not libtcod.console_is_window_closed():
        # render everything
        render_all()

        libtcod.console_flush()

        # erase objects so they can be drawn to new locations
        for object in objects:
            object.clear()

        # get keyboard input, exit game if needed
        player_action = handle_keys()
        if player_action == 'exit':
            save_game()
            break

        # execute monster AI
        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.ai:
                    object.ai.take_turn()

        if monster_count == 0:
            message('0 monsters remain! You feel yourself falling...', libtcod.light_green)
            dungeon_level += 1
            new_level()

###########
# NEW GAMES
###########

# generates a new level, keeping old player stats
def new_level():
    make_map()
    initialize_fov()
    render_all(first_render = True)

# starts a new game
def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level

    #create player object
    fighter_component = Fighter(hp = 30, defense = 2, power = 5, mana=10, spell_damage=0, death_function = player_death)
    player = Object(0, 0, '@', 'player', libtcod.white, blocks = True, fighter = fighter_component, level=1)


    # generate random map
    make_map(first_render = True)

    # generate field of view based on map
    initialize_fov()

    # set gamestate
    game_state = 'playing'

    # create inventory and message lists
    inventory = []
    game_msgs = []

    #set the dungeon level
    if dungeon_level != 0:
        dungeon_level = 0

    # print welcome message
    message('Welcome to Hackin\'s Lash. For many years, a cruel dictator named Hackin has ruled the Dungeons of Demise. You must rise up and strike him down! Press ESC for help.', libtcod.white)
    message('You are level ' + str(player.level) + '.', libtcod.yellow)

##################
# LOADING & SAVING
##################

# saves the game to the working directory
def save_game():
    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player)
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['monster_count'] = monster_count
    file['dungeon_level'] = dungeon_level
    file.close()

# loads the savefile from the working directory if there is one
def load_game():
    global map, objects, player, inventory, game_msgs, game_state, monster_count, dungeon_level

    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    monster_count = file['monster_count']
    dungeon_level = file['dungeon_level']
    file.close()

    initialize_fov()
    
############
# ENTRYPOINT
############
main_menu()
