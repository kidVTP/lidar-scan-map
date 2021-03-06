"""
Analyze scan data points and find set of best fit lines.
Plot points and lines. Display and save plot image.
"""

import math
import matplotlib.pyplot as plt
from matplotlib import style
import os
from pprint import pprint

style.use('fivethirtyeight')
filename = "scanMaps/scanMap"

# detection level thesholds
GAP = 6
CORNER = 6

# global values
points = []  # list of point type items

# utility functions for working with 2D points and lines
# a point (x, y) is represented by its x, y coordinates
# a line (a, b, c) is represented by the eqn: ax + by + c = 0

def cnvrt_2pts_to_coef(pt1, pt2):
    """Return (a,b,c) coef of line defined by 2 (x,y) pts."""
    x1, y1 = pt1
    x2, y2 = pt2
    a = y2 - y1
    b = x1 - x2
    c = x2*y1-x1*y2
    return (a, b, c)

def proj_pt_on_line(line, pt):
    """Return point which is the projection of pt on line."""
    a, b, c = line
    x, y = pt
    denom = a**2 + b**2
    if not denom:
        return pt
    xp = (b**2*x - a*b*y -a*c)/denom
    yp = (a**2*y - a*b*x -b*c)/denom
    return (xp, yp)

def p2p_dist(p1, p2):
    """Return the distance between two points"""
    x, y = p1
    u, v = p2
    return math.sqrt((x-u)**2 + (y-v)**2)

def p2p_angle(p0, p1):
    """Return angle (degrees) from p0 to p1."""
    return math.atan2(p1[1]-p0[1], p1[0]-p0[0])*180/math.pi

def p2line_dist(pt, line):
    """Return perpendicular distance between pt & line"""
    p0 = proj_pt_on_line(line, pt)
    return p2p_dist(pt, p0)


class Point():
    """Convenience structure encapsulating data point measured values

    (int type) and calculated values (float type)"""

    def __init__(self, dist, enc_val, lev=0, theta=0, xy=(0, 0)):
        self.dist = dist  # integer measured distance (cm)
        self.enc_val = enc_val  # integer angle encoder value
        self.lev = lev  # float linearized encoder value
        self.theta = theta  # (derived) float angle wrt car (radians)
        self.xy = xy  # (x, y) coordinates


def find_corners(regions):
    """Within each continuous region, find index and value of data point
    located farthest from the end_to_end line segment if value > CORNERS.
    If index found, split region(s) at index & return True."""
    corners = []
    found = False
    for region in regions:
        max_dist = 0
        max_idx = 0
        idx1 = region[0]
        idx2 = region[-1]
        p1 = (points[idx1].xy)
        p2 = (points[idx2].xy)
        line = cnvrt_2pts_to_coef(p1, p2)
        for n in range(idx1, idx2):
            pnt = (points[n].xy)
            dist = p2line_dist(pnt, line)
            if dist > max_dist:
                max_dist = dist
                max_idx = n
        if max_dist > CORNER:
            corners.append(max_idx)
    # Insert found corners into regions. Start with high values of index
    # first to avoid problems when popping and inserting into regions.
    if corners:
        found = True
        corners.reverse()
        for corner_index in corners:
            for n, region in enumerate(regions):
                if region[0] < corner_index < region[-1]:
                    start, end = regions.pop(n)
                    regions.insert(n, (start, corner_index))
                    regions.insert(n+1, (corner_index+1, end))
    return found

def _find_continuous_regions():
    """Find continuous regions of closely spaced points (clumps)
    Large gaps (dist to neighbor > GAP) represent 'edges' of regions.
    Record index of the start & end points of each region.
    Return list of regions.
    """
    global points

    regions = []  # list of regions
    start_index = 0  # index of start of first region
    gap = 0
    for n, pnt in enumerate(points):
        if n:  # skip first point because there is no 'previous'
            gap = abs(pnt.dist - points[n-1].dist)
        if gap > GAP:
            if n > (start_index + 1):
                regions.append((start_index, n-1))
            start_index = n
    regions.append((start_index, n))  # append final region in loop above
    return regions


def find_segments(data):
    """
    Read raw scan_data (list) in which each line contains 4 vlues:
    encoder_count, distance, byte_count, delta_time.
    Populate global points (list of points) and return
    regions, a list of pairs of index values representing
    the end points of straight line segments that fit the data.
    """
    global points
    print("gap threshold = ", GAP)
    print("corner threshold = ", CORNER)
    for item in data:
        enc_cnt = item[0]
        dist = item[1]
        # map only data from center 180 degrees of rotation
        if 10000 <= enc_cnt <= 30000:
            pnt = Point(dist, enc_cnt)
            points.append(pnt)
    print("Initial number of raw data points = ", len(points))

    # encoder count values go from 0 (straight behind)
    # and increase with CW rotation.
    # straight left: enc_val = 10000; theta = pi
    # straight ahead: enc_val = 20000; theta = pi/2
    # straight right: enc_val = 30000; theta = 0
    # (enc_val tops out at 32765, so no info past that)
    # ec_start = points[0].enc_val
    # ec_end = points[-1].enc_val
    for pnt in points:
        theta = 1.5 * math.pi * (1 - (pnt.enc_val / 30000))
        pnt.theta = theta

    # Remove points whose dist value == 1200 (max value)
    cull_list = []
    for n, pnt in enumerate(points):
        if pnt.dist == 1200:
            cull_list.append(n)
    print("Points culled with dist > 1200: ", len(cull_list))
    cull_list.reverse()
    for n in cull_list:
        points.pop(n)

    # Remove points whose dist value == 0
    cull_list = []
    for n, pnt in enumerate(points):
        if pnt.dist == 0:
            cull_list.append(n)
    print("Points culled with dist == 0: ", len(cull_list))
    cull_list.reverse()
    for n in cull_list:
        points.pop(n)

    # convert polar coords (dist, theta) to (x, y) coords
    for pnt in points:
        x = pnt.dist * math.cos(pnt.theta)
        y = pnt.dist * math.sin(pnt.theta)
        pnt.xy = (x, y)

    # Find continuous regions of closely spaced points (delta dist < GAP)
    regions = _find_continuous_regions()

    # Discard points in regions having fewer than 4 points
    to_discard = []
    for n, region in enumerate(regions):
        if region[-1] - region[0] < 4:
            for idx in range(region[0]-1, region[-1]):
                to_discard.append(idx)
    print("Points discarded from tiny regions", len(to_discard))
    to_discard.reverse()
    for idx in to_discard:
        points.pop(idx)

    # Find continuous regions (again) with revised list of points
    regions = _find_continuous_regions()

    # find (and discard) 'solo' points between continuous regions
    solo_points = []
    top_of_prev_region = -1
    for region in regions:
        nbr = region[0] - top_of_prev_region - 1  # nmbr_of_solo_pts:
        if nbr:
            idx = top_of_prev_region
            for n in range(nbr):
                idx += 1
                solo_points.append(idx)
        top_of_prev_region = region[-1]
    print("'solo' points (not in a region) discarded: ", len(solo_points))
    solo_points.reverse()
    for idx in solo_points:
        points.pop(idx)

    # Find continuous regions (again) with revised list of points
    regions = _find_continuous_regions()

    print("Continuous regions: ", regions)

    # If the points in a continuous region are substantially straight &
    # linear, they can be well represented by a straight line segment
    # between the start and end points of the region.
    # However, if the points trace an 'L' shape, as they would where two
    # walls meet at a corner, two straight line segments would be needed,
    # with the two segments meeting at the corner.
    # To find a corner in a region, look for the point at the greatest
    # distance from the straight line joining the region end points.
    # Only one corner is found at a time. To find multiple corners in a
    # region (a zig-zag shaped wall, for example) make multiple passes.

    pass_nr = 0
    while find_corners(regions):
        pass_nr += 1
        print("Look for corners, pass %s:" % pass_nr)
        print("Regions: ", regions)
    return regions

def show_map(data, nmbr=None):
    global points
    points = []
    segments = find_segments(data)
    if nmbr:
        imagefile = filename + str(nmbr) + ".png"
    else:
        imagefile = filename + ".png"

    # plot data points & line segments
    xs = []
    ys = []
    for pnt in points:
        x, y = pnt.xy
        xs.append(x)
        ys.append(y)
    plt.scatter(xs, ys, color='#003F72')
    title = "(%s pts) " % len(points)
    title += "GAP: %s, CORNER: %s" % (GAP, CORNER)
    plt.title(title)
    line_coords = []  # x, y coordinates
    for segment in segments:
        start, end = segment
        x_vals = [xs[start], xs[end]]
        y_vals = [ys[start], ys[end]]
        line_coords.append(((xs[start], ys[start]), (xs[end], ys[end])))
        plt.plot(x_vals, y_vals)
    pprint(line_coords)
    plt.axis('equal')
    plt.savefig(imagefile)
    plt.clf()  # clears previous points & lines
    #plt.show()  # shows interactive plot
