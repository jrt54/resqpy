Cellular Grid Basics
====================

This page is under construction

This tutorial page introduces some basic concepts and methods for working with cellular grids in resqpy. Cellular grids are the most complex of the RESQML object classes and further material will be presented in later tutorials. This page does not cover RESQML 2D grids, for which resqpy uses the term mesh.

RESQML cellular grid classes
----------------------------
By cellular grid, we mean a data structure that divides up a finite 3D space into cells, each of which has a defined geometry. The RESQML standard differentiates between 3 primary classes of cellular grid, depending on how the cells are indexed:

* IjkGridRepresentation, where each cell is indexed by three integers – the most commonly used form
* UnstructuredColumnLayerGridRepresentation, with cells indexed by two integers – where the column pattern in plan view is unstructured, perhaps constructed on a perpendicular bisector (pebi) basis, yet there is still a clearly defined layering
* UnstructuredGridRepresentation, with cells indexed by a single integer – where there are no constraints on the shape or arrangement of cells

Two more classes of grid are similar to the first two above but allow for some of the cells to be further split (typically by a fault plane) and therefore have locally varying number of faces and indexing:

* TruncatedIjkGridRepresentation
* TruncatedUnstructuredColumnLayerGridRepresentation

One further RESQML class is rather ill-defined and caters for research grids:

* GpGridRepresentation – the Gp stands for general purpose

Of these six RESQML classes only the first, obj_IjkGridRepresentation, has currently been implemented in resqpy. The equivalent resqpy class is Grid, though a derived class, RegularGrid, can be used to construct simple block grids.

IJK grid variants
-----------------
The RESQML IjkGridRepresentation class includes optional attributes that allow for various grid features:

* Explicitly defined (irregular) or regular geometry
* Radial or cartesian grid geometry
* Fully defined or with missing geometry
* Unfaulted or faulted
* With or without gaps between layers
* With or without gaps between I or J slices

These are discussed in the following paragraphs.

Explicitly defined or regular geometry
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The RESQML schema definition uses abstract classes to allow some conceptual objects to be represented in different ways. A grid geometry may be defined explicitly, with the xyz location of each cell corner point held in the dataset. Alternatively, if the cells have a regular cuboid shape, the size and number of these cells can be succinctly stored without saving all the corner point information. (The presentation here, of two possibilities, is actually a simplification of multiple options that are available in the standard.)

Note that the implication of the IJK grid concept is that cells, for the most part, share faces with their logical neighbours in the three logical dimensions of I, J & K even in the case of an explicitly defined geometry. For this reason, the storage of corner point locations is such that there is no duplication of data where a corner point is shared between multiple cells. When faces and corner points are not shared, for example due to faulting, data structures in the RESQML schema can represent this and these situations are discussed in later paragraphs.

At present, resqpy only handles explicitly defined grid geometries. The resqpy RegularGrid class can be used to construct grids with regular geometry but at present this generates an explicit corner point representation for persistent storage.

Radial or cartesian geometry
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Given an explicit representation of grid geometry, the actual pattern of cells in physical xyz space is very flexible, subject to the condition that the geometry is predominantly continuous, ie. with cells that are neighbours in IJK space mostly sharing faces. Therefore to represent a radial grid, the only real difference in the RESQML data is the inclusion of an optional boolean flag, RadialGridIsComplete, which indicates that the last slice in the J dimension should be considered to be a neighbour of the first slice. A further data structure – radial origin polyline – is required for regular radial grids. With such radial grids, the I index varies radially away from the centre of the grid, and the J index varies in the angular (theta) direction. Of course, in the case of an explicit grid, the corner point locations will need to have been generated appropriately.

The resqpy Grid class has been written with 'cartesian' (ie. non-radial) grids in mind. In particular, methods working with the geometry of individual cells assume them to have a hexahedral geometry, which is not the intention for cells in radial grids. Therefore at present radial grids are not supported by resqpy.

Fully defined or with missing geometry
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
For explicitly defined grid geometries, the RESQML standard allows for some parts of the geometry to be flagged as missing (not defined). This can be indicated with a boolean array holding a value for each pillar (also known as a coordinate line) and/or another array holding a value for each cell. It is recommended that the numpy NaN (not a number) value is used in the corner point array where the geometry is missing.

The resqpy Grid class handles these missing geometry options. However, some of the higher level resqpy functionality, such as finding the intersection of a well trajectory with a grid, require the geometry to be complete. To facilitate this, one of the Grid methods – set_geometry_is_defined() – can optionally generate geometry where it is missing (and mark such cells as inactive).

Unfaulted or faulted
^^^^^^^^^^^^^^^^^^^^
A grid may be unfaulted, in which case all cells share their faces with any logically neighbouring cells (with the exception of gaps, discussed in the following paragraphs). In this case the corner point data is fully shared between cells and the array has the shape (NK + 1, NJ + 1, NI + 1, 3) with the final axis covering the x,y,z values for each point.

If, however, a grid involves some faults with throw, then some of the pillars are split, with different sets of xyz data for the two sides of the fault. (And where two faults cross, a single pillar may be split four ways.) In the RESQML data, the extra pillar data is represented by flattening the middle two dimensions of the corner point data into a single 'pillar' axis, and then extending that axis with the required number of extra sets of pillar data. This means the corner point array has the shape (NK + 1, (NJ + 1) * (NI + 1) + NE, 3) where NE is the number of extra sets of pillar data due to splitting. Some extra integer arrays are also required to identify which of the original pillars are split and which columns of cells the extra pillar data pertain to.

Both the RESQML IjkGridRepresentation class and the resqpy Grid class contain a simple boolean flag indicating whether any split pillars are present or not. In general the resqpy code fully supports both faulted and unfaulted grids.

The resqpy Grid class also contains a method –unsplit_points_ref() – for returning an unsplit version of the corner point array. That method is rather simplistic and the higher level derived_model module contains functions which can modify the throw on faults in more complex ways.

With or without gaps between layers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The RESQML usage guide recommends against building cellular grids with unrepresented voids between cells. However, the schema definition does allow for this. In the case of an IJK grid, a gap can exist between layers and this is referred to as a 'K gap'. When K gaps are present, an extra boolean array indicates which layers in the model have a K gap immediately 'afterwards' (which usually means below). The first axis of the corner point data is enlarged to provide two slices of points data between layers where there is a gap (instead of the normal one, shared, slice).

The resqpy code can generally handle grids with K gaps.

With or without gaps between I or J slices
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
As with K gaps, the RESQML standard also allows for gaps between I or J slices of cells. However, the resqpy code does not support this. (Though the same geometry can be represented with split pillars as there is no requirement that the split pillar data lie on a single coordinate line in space.)

The resqpy Grid class
---------------------
The resqpy grid module contains the class Grid, which handles RESQML IjkGridRepresentation objects. A Grid object has several attributes (which calling code can refer to directly) and methods, only some of which are introduced here.

Basic Grid attributes
The following are just a few of the attributes which calling code is likely to access directly.

* model: the 'parent' model.Model object
* uuid
* grid_root: the xml root node
* extent_kji: a triplet of integers containing the size of the grid (nk, nj, ni)
* ni, nj, nk: separate integer attributes, duplicating the information in extent_kji for convenience
* crs_uuid
* crs_root: the xml root node of the coordinate reference system used by the grid
* inactive: a numpy boolean array of shape extent_kji, indicating which cells are inactive
* property_collection: a property.PropertyCollection object holding the properties associated with the grid
* has_split_coordinate_lines: a boolean indicating whether the grid has any split pillars (ie. is faulted)

Basic Grid methods
------------------
Of the many methods provided by the Grid class, the following are the most commonly used. Refer to the docstrings for more information, including argument lists.

* cell_count(): returns the number of cells in the grid, optionally only counting those with geometry, or not pinched out, or active
* natural_cell_index(), natural_cell_indices(): converts cell index from triple index form (k, j, i) to single integer (for flattened array)
* denaturalized_cell_index(), denaturalized_cell_indices(): the opposite of the methods above
* cell_geometry_is_defined(): returns boolean indicating whether a cell has geometry
* pillar_geometry_is_defined(): returns boolean indicating whether a pillar has any geometry
* geometry_defined_for_all_cells(): returns single boolean
* geometry_defined_for_all_pillars(): returns single boolean
* cache_all_geometry_arrays(): ensures all the grid's geometry arrays are loaded as attributes
* create_column_pillar_mapping(): returns a numpy int array of shape (nj, ni, 2, 2) with pillar index for each corner of each column
* points_ref(): returns (and caches) the xyz points array, by default as a masked array based on NaN values
* xyz_box(): returns a numpy float array of shape (2, 3) holding the min and max xyz values
* split_horizon_points(): returns a numpy float array of shape (nj, ni, 2, 2, 3) being all corner points for a horizon (layer interface)
* split_x_section_points(): similar to above for a cross section (I or J interface)
* coordinate_line_end_points(): returns a numpy float array of shape (nj+1, ni+1, 2, 3) holding xyz points defining straight pillar lines
* z_corner_point_depths(): returns a numpy float array of shape (nk, nj, ni, 2, 2, 2) holding depth (z) values for cell corner points
* corner_points(): returns a numpy float array of shape (nk, nj, ni, 2, 2, 2, 3) holding the fully expanded corner points of each cell
* centre_point(): returns a numpy float array of shape (nk, nj, ni, 3) holding the centre point (mean of 8 corners) of each cell
* thickness(): returns a numpy float array of shape (nk, nj, ni) holding the thickness of each cell
* volume(): returns a numpy float array of shape (nk, nj, ni) holding the volume of each cell
* pinched_out(): returns a numpy boolean array of shape (nk, nj, ni) indicating which cells are completely pinched out
* interpolated_point(): returns the xyz location of a tri-linear interpolation of a point in a unit cube when mapped onto a cell
* face_centre(): returns the xyz location of the centre of one face of a cell
* interface_vector(): for one of the IJK axes, returns the vector from the centre of the negative face to the centre of the positive for a cell
* z_inc_down(): convenience method returning the boolean flag from the crs, indicating whether z is increasing downwards
* xy_units(): convenience method returning the units of measure of x & y, from the crs
* z_units(): convenience method returning the units of measure of z, from the crs
* off_handed(): returns True if the handedness of the IJK axes differs from that of the xyz axes, otherwise False
* find_cell_for_point_xy(): searches top of grid in 2D to find column containing a given xy point

A couple more methods are needed when writing a Grid object:

* write_hdf5_from_caches()
* create_xml()

There are several other methods in the Grid class, and many of those above can be used in more than one way. The olio.grid_functions module contains some higher level functions for specialist grid operations and the derived_model module contains many functions for modifying grid geometries.

Reading a Grid object
---------------------
In this tutorial the examples refer to the S-bend dataset and assume that the .epc and .h5 files have already been generated (see earlier tutorial).

First open a Model object in the usual way:

.. code-block:: python

    import resqpy.model as rq
    import resqpy.grid as grr
    model = rq.Model('s_bend.epc')

If your model is known to have only one grid object, or one grid titled 'ROOT', the model class convenience function grid() can be used:

.. code-block:: python

    grid = model.grid()

In the more general case, you will need to identify the desired RESQML object amongst potentially many grids. If the citation title for the desired grid is known and unique, the same Model method can be used, for example:

.. code-block:: python

    grid = model.grid(title = 'FAULTED GRID')

Alternatively, the initialiser for the Grid class can be called directly with something like:

.. code-block:: python

    grid_root = model.root(obj_type = 'IjkGridRepresentation', multiple_handling = 'newest')
    grid = grr.Grid(model, grid_root = grid_root)
