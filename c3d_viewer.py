# Copyright (c) 2010 Leif Johnson <leif@leifjohnson.net>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

'''A simple OpenGL viewer for C3D files.'''

import sys
import math
import time
import optparse
import collections

from itertools import izip as zip

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

import c3d

FLAGS = optparse.OptionParser(usage='python c3d_viewer.py [OPTIONS] FILE...')

BLACK = (0, 0, 0)
WHITE = (1, 1, 1)
RED = (1, 0.2, 0.2)
YELLOW = (1, 1, 0.2)
ORANGE = (1, 0.7, 0.2)
GREEN = (0.2, 0.9, 0.2)
BLUE = (0.2, 0.3, 0.9)
COLORS = (WHITE, RED, YELLOW, GREEN, BLUE, ORANGE)


class Viewer(object):
    '''Render data from a C3D file using OpenGL.'''

    def __init__(self, c3d_reader):
        '''Set up this viewer with some initial parameters.'''
        # we get frames from the c3d file.
        self._frames = c3d_reader.read_frames()
        self._frame_rate = c3d_reader.frame_rate()

        self.maxlen = 1
        self.visible = [True for _ in xrange(c3d_reader.num_points())]
        self._trails = [[] for _ in xrange(c3d_reader.num_points())]
        self._reset_trails()

        # rendering state.
        self.theta = 350.0
        self.phi = 300.0
        self.rho = 1.0
        self.paused = False

        self._last_time = 0
        self._mouse_button = None
        self._width = 800
        self._height = 600
        self._d_theta = 0
        self._d_phi = 0
        self._d_rho = 1.0

        # gl initialization.
        glutInit([])
        glutInitDisplayMode(GLUT_RGBA | GLUT_DEPTH | GLUT_DOUBLE)
        glutInitWindowPosition(0, 0)
        glutInitWindowSize(800, 600)
        glutCreateWindow('C3D Viewer')
        glutKeyboardFunc(self.handle_keypress)
        glutSpecialFunc(self.handle_special_keypress)
        glutDisplayFunc(self.handle_draw)
        glutReshapeFunc(self.handle_reshape)
        glutMotionFunc(self.handle_mouse_movement)
        glutMouseFunc(self.handle_mouse_button)
        glutIdleFunc(self.handle_idle)

        glEnable(GL_COLOR_MATERIAL)
        glEnable(GL_LINE_SMOOTH)
        glEnable(GL_NORMALIZE)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)

        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_LIGHT1)
        glEnable(GL_LIGHT2)

        glShadeModel(GL_SMOOTH)
        glDepthFunc(GL_LEQUAL)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        self._model_list = glGenLists(1)

    def _reset_trails(self):
        self._trails = [collections.deque(t, self.maxlen) for t in self._trails]

    def mainloop(self):
        '''Run the GLUT main loop, blocking until it returns.'''
        glutMainLoop()

    def handle_reshape(self, width, height):
        '''GLUT window reshape callback.'''
        self._width = width
        self._height = height

    def handle_mouse_button(self, button, state, x, y):
        '''GLUT mouse button callback.'''
        if state == GLUT_UP:
            self._mouse_button = None
            self._d_theta = 0
            self._d_phi = 0
            self._d_rho = 1.0
            return
        self._mouse_button = (button, glutGetModifiers())
        self.handle_mouse_movement(x, y)

    def handle_mouse_movement(self, x, y):
        '''GLUT mouse motion callback.'''
        button, modifier = self._mouse_button
        if button == GLUT_LEFT_BUTTON:
            if modifier & GLUT_ACTIVE_CTRL:
                button = GLUT_MIDDLE_BUTTON
            if modifier & GLUT_ACTIVE_ALT:
                button = GLUT_RIGHT_BUTTON

        cx = self._width / 2
        cy = self._height / 2
        if button == GLUT_LEFT_BUTTON:
            self._d_phi = 5 * float(y - cy) / self._height
            self._d_theta = 5 * float(x - cx) / self._width
        if button == GLUT_MIDDLE_BUTTON:
            pass
        if button == GLUT_RIGHT_BUTTON:
            self._d_rho = math.exp(float(y - cy) / self._height / 1.3)

    def handle_keypress(self, char, x, y):
        '''GLUT keyboard callback.'''
        if char == 'q':
            sys.exit(0)
        elif char in '0123456789':
            self.visible[int(char)] ^= True
        elif char == 'p':
            self.paused ^= True
        elif char in '+=':
            self.maxlen *= 2
            self._reset_trails()
        elif char in '_-':
            self.maxlen = max(1, self.maxlen / 2)
            self._reset_trails()

    def handle_special_keypress(self, key, x, y):
        '''GLUT special key callback.'''
        if key == GLUT_KEY_PAGE_UP:
            self.rho /= 1.5
        elif key == GLUT_KEY_PAGE_DOWN:
            self.rho *= 1.5
        elif key == GLUT_KEY_UP:
            self.phi += 5
        elif key == GLUT_KEY_DOWN:
            self.phi -= 5
        elif key == GLUT_KEY_LEFT:
            self.theta -= 5
        elif key == GLUT_KEY_RIGHT:
            self.theta += 5

    def handle_draw(self):
        '''GLUT render callback.'''
        glClearColor(0.9, 0.9, 0.9, 1)
        glClearDepth(1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        self.render_model()

        w = int(2 * self._width / 3.0)
        h = int(self._height / 3.0)

        # show a perspective rendering of the markers.
        glViewport(0, 0, w, self._height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, float(w) / self._height, 0.01, 10)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glTranslate(0, 0, -1)
        glRotate(self.phi, 1, 0, 0)
        glRotate(self.theta, 0, 0, 1)
        glScalef(self.rho, self.rho, self.rho)
        glCallList(self._model_list)
        glPopMatrix()

        # render orthographic projections of the data.
        z = 1.0 / self.rho / 2
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(-z, z, -z, z, -z, z)

        # show the x-y plane.
        glViewport(w, 0, w / 2, h)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glTranslate(0, 0, -1)
        glScalef(2, 2, 2)
        glCallList(self._model_list)
        glPopMatrix()

        # show the y-z plane.
        glViewport(w, h, w / 2, h)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glRotate(-90, 1, 0, 0)
        glTranslate(0, 0, -1)
        glScalef(2, 2, 2)
        glCallList(self._model_list)
        glPopMatrix()

        # show the x-z plane.
        glViewport(w, 2 * h, w / 2, h)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glRotate(-90, 1, 0, 0)
        glRotate(-90, 0, 0, 1)
        glTranslate(0, 0, -1)
        glScalef(2, 2, 2)
        glCallList(self._model_list)
        glPopMatrix()

        glutSwapBuffers()

    def handle_idle(self):
        '''Redraw the scene.'''
        self.theta += self._d_theta
        self.phi += self._d_phi
        self.rho /= self._d_rho

        if self.paused:
            return

        elapsed = time.time() - self._last_time
        if elapsed > 1.0 / self._frame_rate:
            points, analog = self._frames.next()
            for trail, point in zip(self._trails, points):
                trail.append(point[:3])
            self._last_time = time.time()
        else:
            time.sleep(1.0 / self._frame_rate - elapsed)

        glutPostRedisplay()

    def render_model(self):
        '''Render the objects in the world.'''
        glNewList(self._model_list, GL_COMPILE)

        glLightfv(GL_LIGHT0, GL_POSITION, [1, 1, 1, 0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1, 1, 1, 0.5])
        glLightfv(GL_LIGHT0, GL_SPECULAR, [1, 1, 1, 0.5])

        glLightfv(GL_LIGHT1, GL_POSITION, [1, 0, 0, 1])
        glLightfv(GL_LIGHT1, GL_DIFFUSE, [1, 0, 0, 0.8])
        glLightfv(GL_LIGHT1, GL_SPECULAR, [1, 0, 0, 0.8])

        glLightfv(GL_LIGHT2, GL_POSITION, [0, 1, 0, 1])
        glLightfv(GL_LIGHT2, GL_DIFFUSE, [0, 1, 0, 0.8])
        glLightfv(GL_LIGHT2, GL_SPECULAR, [0, 1, 0, 0.8])

        glLightfv(GL_LIGHT3, GL_POSITION, [0, 0, 1, 1])
        glLightfv(GL_LIGHT3, GL_DIFFUSE, [0, 0, 1, 0.8])
        glLightfv(GL_LIGHT3, GL_SPECULAR, [0, 0, 1, 0.8])

        # render a simple axis system
        glLineWidth(1.0)
        glBegin(GL_LINES)
        glColor4f(1, 0, 0, 1)
        glVertex3f(0, 0, 0)
        glVertex3f(100.0, 0, 0)
        glColor4f(0, 1, 0, 1)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 100.0, 0)
        glColor4f(0, 0, 1, 1)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 100.0)
        glEnd()

        # draw markers for the currently maintained data
        for i, points in enumerate(self._trails):
            if not self.visible[i]:
                continue
            self.render_marker_points(str(i), COLORS[i % len(COLORS)], points)

        glEndList()

    def render_marker_points(self, label, color, points):
        glColor4f(*(color + (0.7, )))
        for point in points:
            glPushMatrix()
            glTranslated(*point)
            glutSolidSphere(1.0 / self.rho / 200.0, 13, 13)
            glPopMatrix()

    def render_marker_trails(self, color, points):
        glColor4f(*(color + (0.7, )))
        glBegin(GL_LINES)
        for point in points:
            glVertex3f(*point)
        glEnd()


if __name__ == '__main__':
    opts, args = FLAGS.parse_args()
    if not args:
        FLAGS.error('no input file provided!')

    for filename in args:
        try:
            Viewer(c3d.Reader(open(filename, 'rb'))).mainloop()
        except StopIteration:
            pass
