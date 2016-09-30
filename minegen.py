#!/usr/bin/env python

import argparse
from base64 import encodestring as b64_encode_string
from collections import defaultdict
from cStringIO import StringIO
from gzip import GzipFile
import sys


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--output', '-o',
        help='File to write to (default: stdout)',
        type=argparse.FileType('w'),
        default=sys.stdout,
        action='store',
    )
    parser.add_argument(
        '--direction',
        help='Direction to run the belts (default: up)',
        choices=['up', 'right', 'down', 'left', 'vertical', 'horizontal'],
        default='up',
        action='store',
    )
    parser.add_argument(
        '--lamp',
        help='Include lamps',
        default=False,
        action='store_true',
    )
    parser.add_argument(
        '--belt-type',
        help='Belt type.  Do not specify for yellow belt.  Known types: fast (red), express (blue), purple (bobs logistitcs)',
        default=None,
        action='store',
    )
    parser.add_argument(
        '--debug',
        help='Debug output',
        action='store_true',
    )

    size_group = parser.add_argument_group(
        title='Mine size in tiles',
    )
    size_choice = size_group.add_mutually_exclusive_group(required=True)
    size_choice.add_argument(
        '--mine-size',
        help='Size of the patch being mined',
        metavar=('WIDTH', 'HEIGHT'),
        nargs=2,
        action='store',
        type=int,
    )
    size_choice.add_argument(
        '--edge-coords',
        help='Edges of the patch being mined',
        metavar=('TOP', 'RIGHT', 'BOTTOM', 'LEFT'),
        nargs=4,
        action='store',
        type=int,
    )

    defence_group = parser.add_argument_group(
        title='Defence options',
    )
    defence_group.add_argument(
        '--walls',
        help='Layers of walls',
        nargs='?',
        action='store',
        default=0,
        type=int,
    )

    args = parser.parse_args()

    # args.walls will be 0 if missing, and None if no specified with no option
    if args.walls is None:
        args.walls = 1

    return args


def gz_compress_string(s, level=9):
    buf = StringIO()
    gz = GzipFile(mode='w', fileobj=buf, compresslevel=level)
    gz.write(s)
    gz.close()
    buf.seek(0)
    return buf.read()


class Blueprint(object):
    def __init__(self):
        self._entities = defaultdict(list)
        self.left = 0
        self.right = 0
        self.top = 0
        self.bottom = 0

    def add_entity(self, entity):
        self._entities[entity.name].append(entity)

        if entity.x - entity.left_pad < self.left:
            self.left = entity.x - entity.left_pad
        if entity.x + entity.right_pad > self.right:
            self.right = entity.x + entity.right_pad
        if entity.y - entity.top_pad < self.top:
            self.top = entity.y - entity.top_pad
        if entity.y + entity.bottom_pad > self.bottom:
            self.bottom = entity.y + entity.bottom_pad

    @property
    def width(self):
        return (self.right - self.left) + 1

    @property
    def height(self):
        return (self.bottom - self.top) + 1

    def entities(self):
        for entities in self._entities.itervalues():
            for entity in entities:
                yield entity

    def render(self, stream):
        offset_x = self.right - (self.width / 2)
        offset_y = self.bottom - (self.height / 2)

        first = True
        for entity in self.entities():
            if not first:
                stream.write(',')
            first = False
            stream.write(entity.render(offset_x, offset_y))
            stream.write('\n')

    def draw(self):
        offset_x = -self.left
        offset_y = -self.top
        buf = [[' '] * self.width for _ in xrange(self.height)]
        for entity in self.entities():
            entity.draw(buf, offset_x, offset_y)
        for line in buf:
            print ''.join(line)
        for name, entities in self._entities.iteritems():
            print '{name}: {count}'.format(name=name, count=len(entities))


class Entity(object):
    Up = 0
    Right = 2
    Down = 4
    Left = 6

    right_pad = 0
    left_pad = 0
    top_pad = 0
    bottom_pad = 0

    def __init__(self, name, p, direction):
        self.name = name
        self.x = p[0]
        self.y = p[1]
        self.direction = direction

    def render(self, offset_x, offset_y):
        s = '{{name="{name}",position={{x={x},y={y}}}'.format(
            name=self.name,
            x=self.x - offset_x,
            y=self.y - offset_y,
        )
        if self.direction:
            s += ',direction={direction}'.format(direction=self.direction)
        s += '}'
        return s


class Belt(Entity):
    def __init__(self, p, direction, belt_type):
        if belt_type is None:
            belt_type = 'transport-belt'
        else:
            belt_type = '{belt_type}-transport-belt'.format(belt_type=belt_type)
        Entity.__init__(self, belt_type, p, direction)

    def draw(self, buf, offset_x, offset_y):
        assert buf[self.y + offset_y][self.x + offset_x] == ' '
        if self.direction == Entity.Up:
            buf[self.y + offset_y][self.x + offset_x] = '^'
        if self.direction == Entity.Down:
            buf[self.y + offset_y][self.x + offset_x] = 'v'
        if self.direction == Entity.Left:
            buf[self.y + offset_y][self.x + offset_x] = '<'
        if self.direction == Entity.Right:
            buf[self.y + offset_y][self.x + offset_x] = '>'


class Drill(Entity):
    left_pad = 1
    right_pad = 1
    top_pad = 1
    bottom_pad = 1

    def __init__(self, p, direction):
        Entity.__init__(self, 'electric-mining-drill', p, direction)

    def draw(self, buf, offset_x, offset_y):
        for y in xrange(-1, 2):
            for x in xrange(-1, 2):
                assert buf[self.y + y + offset_y][self.x + x + offset_x] == ' '
        buf[self.y - 1 + offset_y][self.x - 1 + offset_x] = '+'
        buf[self.y - 1 + offset_y][self.x + 1 + offset_x] = '+'
        buf[self.y + 1 + offset_y][self.x - 1 + offset_x] = '+'
        buf[self.y + 1 + offset_y][self.x + 1 + offset_x] = '+'
        buf[self.y - 1 + offset_y][self.x + offset_x] = '^' if self.direction == Entity.Up else '-'
        buf[self.y + 1 + offset_y][self.x + offset_x] = 'v' if self.direction == Entity.Down else '-'
        buf[self.y + offset_y][self.x - 1 + offset_x] = '<' if self.direction == Entity.Left else '|'
        buf[self.y + offset_y][self.x + 1 + offset_x] = '>' if self.direction == Entity.Right else '|'
        buf[self.y + offset_y][self.x + offset_x] = 'x'


class Light(Entity):
    def __init__(self, p):
        Entity.__init__(self, 'small-lamp', p, 0)

    def draw(self, buf, offset_x, offset_y):
        assert buf[self.y + offset_y][self.x + offset_x] == ' '
        buf[self.y + offset_y][self.x + offset_x] = '*'


class Power(Entity):
    def __init__(self, p):
        Entity.__init__(self, 'medium-electric-pole', p, 0)

    def draw(self, buf, offset_x, offset_y):
        assert buf[self.y + offset_y][self.x + offset_x] == ' '
        buf[self.y + offset_y][self.x + offset_x] = 'Y'


class Wall(Entity):
    def __init__(self, p):
        Entity.__init__(self, 'stone-wall', p, 0)

    def draw(self, buf, offset_x, offset_y):
        assert buf[self.y + offset_y][self.x + offset_x] == ' '
        buf[self.y + offset_y][self.x + offset_x] = '#'


directions = {
    'up': 0,
    'right': 2,
    'down': 4,
    'left': 6,
}


def round_up(amt, mul):
    mod = amt % mul
    if mod:
        amt += (mul - mod)
    return amt


def opposite(direction):
    return (direction + 4) % 8


def add_miners(bp, include_lamp, belt_type, direction, split, size):
    mine_width, mine_height = size

    if direction in (Entity.Up, Entity.Down):
        align = lambda x, y: (x, y)
        drill_direction = Entity.Right
        s = mine_height
        t = mine_width
    else:
        align = lambda x, y: (y, x)
        drill_direction = Entity.Down
        s = mine_width
        t = mine_height

    for u in xrange(0, round_up(s, 9), 9):
        for v in xrange(0, round_up(t, 8), 8):
            bp.add_entity(Power(align(v + 0, u + 3)))
            if include_lamp:
                bp.add_entity(Light(align(v + 0, u + 1)))
                bp.add_entity(Light(align(v + 0, u + 5)))

            # Drills
            for i in xrange(0, 9, 3):
                bp.add_entity(Drill(align(v + 2, u + i), drill_direction))
                bp.add_entity(Drill(align(v + 6, u + i), opposite(drill_direction)))

            # Belts
            for i in xrange(9):
                pos = u + i - 1
                if split and pos > (s / 2):
                    belt_direction = opposite(direction)
                else:
                    belt_direction = direction

                bp.add_entity(Belt(align(v + 4, u + i - 1), belt_direction, belt_type))

        bp.add_entity(Power(align(v + 8, u + 3)))
        if include_lamp:
            bp.add_entity(Light(align(v + 8, u + 1)))
            bp.add_entity(Light(align(v + 8, u + 5)))


def add_walls(bp, layers):
    """Surround the current blueprint with walls"""
    cur_left = bp.left - 6
    cur_right = bp.right + 6
    cur_top = bp.top - 6
    cur_bottom = bp.bottom + 6

    for l in xrange(layers):
        for x in xrange(cur_left, cur_right + 1):
            bp.add_entity(Wall((x, cur_top)))
            bp.add_entity(Wall((x, cur_bottom)))
        for y in xrange(cur_top + 1, cur_bottom):
            bp.add_entity(Wall((cur_left, y)))
            bp.add_entity(Wall((cur_right, y)))

        cur_left -= 1
        cur_right += 1
        cur_top -= 1
        cur_bottom += 1


def main():
    args = parse_args()
    output = StringIO()
    output.write('do local _={entities={')

    if args.mine_size:
        size = args.mine_size
    else:
        size = (args.edge_coords[1] - args.edge_coords[3],
                args.edge_coords[2] - args.edge_coords[0])

    if args.direction == 'vertical':
        direction = directions['up']
        split = True
    elif args.direction == 'horizontal':
        direction = directions['left']
        split = True
    else:
        direction = directions[args.direction]
        split = False

    bp = Blueprint()
    add_miners(bp, args.lamp, args.belt_type, direction, split, size)
    if args.walls:
        add_walls(bp, args.walls)
    bp.draw()

    bp.render(output)

    output.write('},icons={{signal={type="item",name="electric-mining-drill"},index=1}}};return _;end')
    output.seek(0)

    if args.debug:
        args.output.write(output.read())
    else:
        args.output.write(b64_encode_string(gz_compress_string(output.read())))

    if args.output == sys.stdout:
        print


if __name__ == '__main__':
    main()
