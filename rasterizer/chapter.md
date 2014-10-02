# A tiny rasterizer

A *rasterizer* is a piece of software that turns descriptions of
shapes into *raster images*, which in turn is just a funny name for
rectangular grids of pixels. The computer screen you probably use
every day has just one such grid of pixels, and so arasterizer, in
some way or another, is at the heart of pretty much every modern
display technology today. Raster images are also used in e-ink
displays and printers (both 2D and 3D!). The graphics you see in laser
shows are maybe the most notable exception.

In this chapter, I will teach you a little about how rasterizers work,
by describing `tiny_gfx`, a simple rasterizer in pure Python. Along
the way we will pick up some techniques that show up repeatedly in
computer graphics code. Having a bit of mathematical background on
linear algebra will help, but I hope the presentation will be
self-contained.

`tiny_gfx` is not practical in many ways. Besides being slow (see
below), the main shortcoming in `tiny_gfx` is that shapes are all of a
single solid color. Still, for 500 lines of code, `tiny_gfx` has a
relatively large set of features:

- alpha blending for semi-transparent colors
- polygonal shapes 
- circles and ellipses
- transformations of shapes (scales, rotations, translations)
- boolean operations on shapes (union, intersection, subtraction)
- antialiasing
- empty space skipping and (relatively) fast rasterization of runs for
  general shapes

Maybe most interestingly, shapes in `tiny_gfx` are extensible. New
shapes are easily added, and they compose well with the other parts of
the code.

## A performance caveat

Rasterizers are so central to display technology that their
performance can make or break a piece of software, and these days the
fastest rasterizers are all seriously specialized technologies, most
of it implemented in custom hardware sitting behind an amazingly
complex device driver. The graphics card in your cellphone is likely rasterizing
polygons in highly parallel processors: 192 cores is a typical
number. It should be no surprise, then, that the rasterizer we will
write here is slow: if CPU-intensive tasks in Python run around 50 times
slower than heavily-optimized, low-level code, and if a graphics
driver has around 200 cores at its disposal, a slowdown of 10,000
times should not be surprising. In reality, `tiny_gfx` is closer to
1,000,000 times slower than the special-purpose graphics rasterizer
from the laptop in which I'm developing it.

# A tour through the modules

## Scene

Most rasterizers do not include the idea of a hierarchical scene graph
in their code, but this is such an important notion in graphics that
I decided to add to this library.

Describing objects hierarchically does to graphics what function
definitions do to programming: it lets us create *composable
abstractions*, pieces that can we put together in interesting ways
without worrying about the internal representation of each piece.

## Shape

The main rasterization loop is in `Shape.draw`, and the two important
abstract methods for subclasses to implement are
`Shape.signed_distance_bound` and `Shape.contains`. These are the
most important methods in the whole module, and we will spend some
time discussing them below.

## Color

The Color object stores a color in RGB, together with
its opacity. It's used both to describe a pixel and to describe the
color of a shape.

## Boolean

This file contains classes used for Boolean operations with
shapes. The base class is `BooleanShape`,
and there's a class for each supported Boolean operation: `Union`,
`Intersection` and `Subtraction`.

## Ellipse

A shape class that describes ellipses. Typical high-speed rasterizers
only support polygons (current hardware typically only supports
triangles, and convert everything to a list of triangles before
sending them to the specialized hardware), but our rasterizer supports
arbitrary shapes. This ellipse class is included as an example of the
kinds of tricks that show up in graphics.

## geometry.py

This file contains geometry classes generally needed for the
rasterizer.

* `Vector`, a 2D vector with your basic operator overloading and
  methods. In this code we use this class to store both points and
  vectors. There are reasons why this is a bad idea, but for sake of
  simplicity and brevity, we do it.

* `AABox`, a 2D axis-aligned bounding box

* `HalfPlane`, a class that models one-half of the 2D plane by a
  linear equation
  
* `Transform`, a class for 2D affine transformations of `Vector`s

* utility functions to build transforms (which should perhaps be
  `classmethod`s of Transform, except that using them leads to long,
  unreadable lines for things that should have short names)

## image

`PPMImage` is a class whose objects will store images that can be
saved in the
[`PPM` format](http://netpbm.sourceforge.net/doc/ppm.html). This
format is the simplest possible format that is still portable and easy
to convert to more popular formats such as `JPEG` and `PNG`.

## poly

`ConvexPoly` represents a convex polygon by a set of
half-planes. `Shape.contains` simply tests all half-planes
corresponding to each edge of the polygon, and
`Shape.signed_distance_bound` takes the most conservative value across
all of the shape half-planes. This actually gives values of 0 for
points on the "infinite line" spanned by polygon edges, but that's
fine because the result needs only be conservative.


# The basics of a rasterizer

The mission of a rasterizer, as we have just seen, is to paint the
two-dimensional grid of pixels with the right colors. Since the color
of one particular pixel is independent of the color of the next pixel,
we can start by thinking from the point of view of a pixel. 

The rasterizer will then answer the question "is pixel X inside shape
Y?". To illustrate, let's start with a very simple shape: a
*half-plane*. A half-plane is what you get when you split the infinite
plane in two using a straight line: the half-plane is just the shape
that contains everything off to any one side of this
line. {{See figure}}

How can we know whether a pixel is to either side of the line? Recall
the equation for a line in the plane, $a.x + b.y + c = 0$. If we
evaluate the expression on the left for a pixel at $(x,y)$ and get a
positive result, we say that the pixel is outside the half-plane. If
we get a negative result, then the pixel is inside the
half-plane. That's all there is to it; all we need to do is check this
expression for every pixel, setting setting the pixel value as
necessary.

The above approach works, but it is wasteful: we are checking the same
expression over and over again for very similar values. The expression
for the half-plane is simple, but more complex shapes will
have costlier expressions. What can we do about this?

The main insight used in the architecture of the rasterizer I'm
presenting here is that knowing the *distance* from a point to the
closest point in the boundary actually tells us a lot about the
shape. The idea is very simple: if we learn that a point is outside a
shape, and the boundary of the shape is 20 pixels away, then any other
pixel within a 20-pixel radius will also be outside. The rasterizer
can skip those pixels safely. Similarly, if we are *inside* the shape,
we can paint more than one pixel for every distance we check.

The trick we use is a little more clever than the paragraph above
suggests. Using the distance to a shape works, but it's not always
easy to compute the distance from a point to the closest point on its
boundary (and sometimes it is very hard!). Instead, we settle for a
procedure that will give us an *lower bound*: we want to know a value
$x$ such as the distance between the point and the shape is *at least
$x$*. With this in hand, we now have some freedom to pick tests: we
want something that is relatively easy to compute (so we do not take
very long checking that one particular pixel), but that is also
relatively accurate (because if the distance bound always returned
trivially zero then we are back to the original problem of checking
every pixel).

This is the fundamental shape interface in `tiny_gfx`'s rasterizer,
then:

    class Shape(SceneObject):
	    ...
        def contains(self, p):
			# returns a boolean
            ...
        def signed_distance_bound(self, p):
            # returns a number

In some sense or another, the way every rasterizer goes fast is by
making as many decisions about which pixels are covered by a shape as
possible using as little computation as possible. Your graphics card
takes this approach to the extreme, by restricting itself to a very
limited set of shapes (very possibly just triangles) and using a
*scanline* technique: by following along the "left" and "right"
borders of a triangle, one can compute the "run" of pixels that
exactly covers a given triangle. In `tiny_gfx` we will be more general
because that's both more fun and more illustrative of computer
graphics ideas.

## A pixel is a region, aliasing

Pixels are usually so small that we tend to think of them as
dimensionless points.

## naive supersampling works, but is slow, and for the same reason!

## Alpha-blending


# Applying the basics to basic shapes

## Half-plane

## Booleans

## convex polygons: intersections of half-planes

## Transformations

## Does a transformation fundamentally change the shape?

## Ellipses

# Where to go from here?

Different colors for different pixels in the triangle. What happens to
our performance tricks? Splitting (the shape in many smaller triangles
doesn't work; why? {{Do I even want to get into this here?}} Talk
about Reyes.)

Making WebGL Dance.

Bresenham's algorithms.

Jim Blinn's corner
