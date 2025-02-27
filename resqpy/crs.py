"""crs.py: RESQML coordinate reference system module."""

version = '10th June 2021'

import logging
log = logging.getLogger(__name__)
log.debug('crs.py version ' + version)

import warnings
import math as maths
import numpy as np
# import xml.etree.ElementTree as et
# from lxml import etree as et

import resqpy.olio.uuid as bu
import resqpy.olio.xml_et as rqet
import resqpy.olio.vector_utilities as vec
import resqpy.olio.weights_and_measures as wam
from resqpy.olio.xml_namespaces import curly_namespace as ns


class Crs():
   """ Coordinate reference system object """

   def __init__(self, parent_model, crs_root = None, uuid = None,
                x_offset = 0.0, y_offset = 0.0, z_offset = 0.0,
                rotation = 0.0, xy_units = 'm', z_units = 'm',
                z_inc_down = True, axis_order = 'easting northing',
                time_units = None, epsg_code = None):
      """Create a new coordinate reference system object.

      arguments:
         parent_model (model.Model): the model to which the new Crs object will belong
         crs_root (xml root node): DEPRECATED – use uuid instead; the xml root node for an existing RESQML crs object
         crs_uuid (uuid.UUID): the uuid of an existing RESQML crs object in model, from which to instantiate the
            resqpy Crs object; if present, all the remaining arguments are ignored
         x_offset, y_offset, z_offset (floats, default zero): the local origin within an implicit parent crs
         rotation (float, default zero): a projected view rotation (in the xy plane), in radians, relative to an
            implicit parent crs
         xy_units (str, default 'm'): the units applicable to x & y values; must be one of the RESQML length uom strings
         z_units (str, default 'm'): the units applicable to z depth values; must be one of the RESQML length uom strings
         z_inc_down (boolean, default True): if True, increasing z values indicate greater depth (ie. in direction of
            gravity); if False, increasing z values indicate greater elevation
         axis_order (str, default 'easting northing'): the compass directions of the positive x and y axes respectively
         time_units (str, optional): if present, the time units of the z values (for seismic datasets), in which case the
            z_units argument is irrelevant
         epsg_code (str, optional): if present, the EPSG code of the implicit parent crs

      returns:
         a new resqpy Crs object

      notes:
         although resqpy does not have full support for identifying a parent crs, the modifiers such as a local origin
         may be used on the assumption that all crs objects refer to the same implicit parent crs;
         there are two equivalent RESQML classes and which one is generated depends on whether the time_units argument
         is used, when instantiating from values;
         it is strongly encourage to call the create_xml() method immediately after instantiation (unless the resqpy
         crs is a temporary object) as the uuid may be modified at that point to re-use any existing equivalent RESQML
         crs object in the model

      :meta common:
      """

      self.model = parent_model

      self.crs_root = None
      if crs_root is not None:
         warnings.warn("Argument crs_root is deprecated, please use uuid")
         uuid = rqet.uuid_for_part_root(crs_root)
         self.crs_root = crs_root

      if uuid is None:
         self.uuid = bu.new_uuid()
      else:
         self.uuid = uuid
         if self.crs_root is None: self.crs_root = self.model.root(uuid = uuid)

      self.xy_units = None
      self.z_units = None
      self.time_units = None   # if None, z values are depth; if not None, z values are time (from seismic)
      self.z_inc_down = None
      self.x_offset = None
      self.y_offset = None
      self.z_offset = None
      self.rotation = None     # radians
      self.axis_order = None
      self.epsg_code = None
      self.rotated = None
      self.rotation_matrix = None
      self.reverse_rotation_matrix = None

      if self.crs_root is not None:
         flavour = rqet.node_type(self.crs_root)
         assert flavour in ['obj_LocalDepth3dCrs', 'obj_LocalTime3dCrs']
         self.xy_units = rqet.find_tag_text(self.crs_root, 'ProjectedUom')
         self.axis_order = rqet.find_tag_text(self.crs_root, 'ProjectedAxisOrder')
         self.z_units = rqet.find_tag_text(self.crs_root, 'VerticalUom')
         self.z_inc_down = rqet.find_tag_bool(self.crs_root, 'ZIncreasingDownward')
         if flavour == 'obj_LocalTime3dCrs':
            self.time_units = rqet.find_tag_text(self.crs_root, 'TimeUom')
         else:
            self.time_units = None
         self.x_offset = rqet.find_tag_float(self.crs_root, 'XOffset')
         self.y_offset = rqet.find_tag_float(self.crs_root, 'YOffset')
         self.z_offset = rqet.find_tag_float(self.crs_root, 'ZOffset')
         self.rotation = rqet.find_tag_float(self.crs_root, 'ArealRotation')  # todo: extract uom attribute from this node
         parent_xy_crs = rqet.find_tag(self.crs_root, 'ProjectedCrs')
         if parent_xy_crs is not None and rqet.node_type(parent_xy_crs) == 'ProjectedCrsEpsgCode':
            self.epsg_code = rqet.find_tag_text(parent_xy_crs, 'EpsgCode')    # should be an integer?
         else:
            self.epsg_code = None

      else:
         if axis_order is not None:
            assert axis_order in ["easting northing", "northing easting", "westing southing", "southing westing",
                                  "northing westing", "westing northing"], 'invalid axis order: ' + str(axis_order)
         self.xy_units = xy_units
         self.z_units = z_units
         self.time_units = time_units
         self.z_inc_down = z_inc_down
         self.x_offset = x_offset
         self.y_offset = y_offset
         self.z_offset = z_offset
         self.rotation = rotation    # radians
         self.axis_order = axis_order
         self.epsg_code = epsg_code

      self.rotated = (not maths.isclose(self.rotation, 0.0, abs_tol = 1e-8) and
                      not maths.isclose(self.rotation, 2.0 * maths.pi, abs_tol = 1e-8))
      if self.rotated:
         self.rotation_matrix = vec.rotation_matrix_3d_axial(2, maths.degrees(self.rotation))
         self.reverse_rotation_matrix = vec.rotation_matrix_3d_axial(2, maths.degrees(-self.rotation))

      self.null_transform = (maths.isclose(self.x_offset, 0.0, abs_tol = 1e-8) and
                             maths.isclose(self.y_offset, 0.0, abs_tol = 1e-8) and
                             maths.isclose(self.z_offset, 0.0, abs_tol = 1e-8) and
                             not self.rotated)


   def is_right_handed_xyz(self):
      """Returns True if the xyz axes are right handed; False if left handed."""

      return self.axis_order in ["northing easting", "southing westing", "westing northing"] == self.z_inc_down


   def global_to_local(self, xyz, global_z_inc_down = True):
      """Convert a single xyz point from the parent coordinate reference system to this one."""

      x, y, z = xyz
      if self.x_offset != 0.0: x -= self.x_offset
      if self.y_offset != 0.0: y -= self.y_offset
      if global_z_inc_down != self.z_inc_down: z = -z
      if self.z_offset != 0.0: z -= self.z_offset
      if self.rotated:
         (x, y, z) = vec.rotate_vector(self.rotation_matrix, np.array((x, y, z)))
      return (x, y, z)


   def global_to_local_array(self, xyz, global_z_inc_down = True):
      """Convert in situ a numpy array of xyz points from the parent coordinate reference system to this one."""

      if self.x_offset != 0.0: xyz[..., 0] -= self.x_offset
      if self.y_offset != 0.0: xyz[..., 1] -= self.y_offset
      if global_z_inc_down != self.z_inc_down:
         z = np.negative(xyz[..., 2])
         xyz[..., 2] = z
      if self.z_offset != 0.0: xyz[..., 2] -= self.z_offset
      if self.rotated:
         a = vec.rotate_array(self.rotation_matrix, xyz)
         xyz[:] = a


   def local_to_global(self, xyz, global_z_inc_down = True):
      """Convert a single xyz point from this coordinate reference system to the parent one."""

      if self.rotated:
         (x, y, z) = vec.rotate_vector(self.reverse_rotation_matrix, np.array(xyz))
      else:
         (x, y, z) = xyz
      if self.x_offset != 0.0: x += self.x_offset
      if self.y_offset != 0.0: y += self.y_offset
      if self.z_offset != 0.0: z += self.z_offset
      if global_z_inc_down != self.z_inc_down: z = -z
      return (x, y, z)


   def local_to_global_array(self, xyz, global_z_inc_down = True):
      """Convert in situ a numpy array of xyz points from this coordinate reference system to the parent one."""

      if self.rotated:
         a = vec.rotate_array(self.reverse_rotation_matrix, xyz)
         xyz[:] = a
      if self.x_offset != 0.0: xyz[..., 0] += self.x_offset
      if self.y_offset != 0.0: xyz[..., 1] += self.y_offset
      if self.z_offset != 0.0: xyz[..., 2] += self.z_offset
      if global_z_inc_down != self.z_inc_down:
         z = np.negative(xyz[..., 2])
         xyz[..., 2] = z


   def has_same_epsg_code(self, other_crs):
      """Returns True if either of the crs'es has a null EPSG code, or if they are the same."""
      if self.epsg_code is None or other_crs.epsg_code is None or self.epsg_code == other_crs.epsg_code: return True
      return False


   def is_equivalent(self, other_crs):
      """Returns True if this crs is effectively the same as the other crs."""

      log.debug('testing crs equivalence')
      if other_crs is None: return False
      if self is other_crs: return True
      if bu.matching_uuids(self.uuid, other_crs.uuid): return True
      if self.xy_units != other_crs.xy_units or self.z_units != other_crs.z_units: return False
      if self.z_inc_down != other_crs.z_inc_down: return False
      if (self.time_units is not None or other_crs.time_units is not None) and self.time_units != other_crs.time_units:
         return False
      if not self.has_same_epsg_code(other_crs): return False
      if self.null_transform and other_crs.null_transform: return True
      if (maths.isclose(self.x_offset, other_crs.x_offset, abs_tol = 1e-4) and
          maths.isclose(self.y_offset, other_crs.y_offset, abs_tol = 1e-4) and
          maths.isclose(self.z_offset, other_crs.z_offset, abs_tol = 1e-4) and
          maths.isclose(self.rotation, other_crs.rotation, abs_tol = 1e-4)): return True
          # todo: handle and check rotation units
      return False


   def __eq__(self, other):
      return self.is_equivalent(other)


   def __ne__(self, other):
      return not self.is_equivalent(other)


   def convert_to(self, other_crs, xyz):
      """Converts a single xyz point from this coordinate reference system to the other.

      :meta common:
      """

      if self is other_crs: return tuple(xyz)
      assert self.has_same_epsg_code(other_crs)
      xyz = self.local_to_global(xyz)
      xyz = (wam.convert_lengths(xyz[0], self.xy_units, other_crs.xy_units),
             wam.convert_lengths(xyz[1], self.xy_units, other_crs.xy_units),
             wam.convert_lengths(xyz[2], self.z_units, other_crs.z_units))
      xyz = other_crs.global_to_local(xyz)
      return tuple(xyz)


   def convert_array_to(self, other_crs, xyz):
      """Converts in situ a numpy array of xyz points from this coordinate reference system to the other.

      :meta common:
      """

      if self.is_equivalent(other_crs): return
      assert self.has_same_epsg_code(other_crs)
      self.local_to_global_array(xyz)
      if self.xy_units == self.z_units and other_crs.xy_units == other_crs.z_units:
         wam.convert_lengths(xyz, self.xy_units, other_crs.xy_units)
      else:
         wam.convert_lengths(xyz[..., :2], self.xy_units, other_crs.xy_units)
         wam.convert_lengths(xyz[..., 2], self.z_units, other_crs.z_units)
      other_crs.global_to_local_array(xyz)
      return xyz


   def convert_from(self, other_crs, xyz):
      """Converts a single xyz point from the other coordinate reference system to this one.

      :meta common:
      """

      if self is other_crs: return tuple(xyz)
      assert self.has_same_epsg_code(other_crs)
      xyz = other_crs.local_to_global(xyz)
      xyz = (wam.convert_lengths(xyz[0], other_crs.xy_units, self.xy_units),
             wam.convert_lengths(xyz[1], other_crs.xy_units, self.xy_units),
             wam.convert_lengths(xyz[2], other_crs.z_units, self.z_units))
      xyz = self.global_to_local(xyz)
      return tuple(xyz)


   def convert_array_from(self, other_crs, xyz):
      """Converts in situ a numpy array of xyz points from the other coordinate reference system to this one.

      :meta common:
      """

      if self.is_equivalent(other_crs): return
      assert self.has_same_epsg_code(other_crs)
      other_crs.local_to_global_array(xyz)
      if self.xy_units == self.z_units and other_crs.xy_units == other_crs.z_units:
         wam.convert_lengths(xyz, other_crs.xy_units, self.xy_units)
      else:
         wam.convert_lengths(xyz[..., :2], other_crs.xy_units, self.xy_units)
         wam.convert_lengths(xyz[..., 2], other_crs.z_units, self.z_units)
      self.global_to_local_array(xyz)
      return xyz


   def create_xml(self, add_as_part = True, root = None, title = 'Coordinate Reference System',
                  originator = None, reuse = True):
      """Creates a Coordinate Reference System xml node and optionally adds as a part in the parent model.

      arguments:
         add_as_part (boolean, default True): if True the newly created crs node is added to the model
            as a part
         root (optional, usually None): if not None, the newly created crs node is appended as a child
            of this node (rarely used)
         title (string): used as the Title text in the citation node
         originator (string, optional): the name of the human being who created the crs object;
            default is to use the login name
         reuse (boolean, default True): if True and an equivalent crs already exists in the model then
            the uuid for this Crs is modified to match that of the existing object and the existing
            xml node is returned without anything new being added

      returns:
         newly created (or reused) coordinate reference system xml node

      notes:
         if the reuse argument is True, it is strongly recommended to call this method immediately after
         a new Crs has been instantiated from explicit values, as the uuid may be modified here;
         if reuse is True, the title is not regarded as important and a match with an existing object
         may occur even if the titles differ

      :meta common:
      """

      if reuse and self.uuid is not None:
         old_root = self.model.root(uuid = self.uuid)
         if old_root is not None:
            return old_root

      flavour = 'LocalDepth3dCrs' if self.time_units is None else 'LocalTime3dCrs'

      if reuse:
         crs_uuids = self.model.uuids(obj_type = flavour)
         for old_crs_uuid in crs_uuids:
            old_crs = Crs(self.model, uuid = old_crs_uuid)
            if old_crs == self:
               old_root = self.model.root(uuid = old_crs_uuid)
               self.uuid = old_crs_uuid
               if self.model.crs_root is None: self.model.crs_root = old_root  # mark's as 'main' crs for model
               return old_root

      crs = self.model.new_obj_node(flavour)

      if self.uuid is None:
         self.uuid = bu.uuid_from_string(crs.attrib['uuid'])
      else:
         crs.attrib['uuid'] = str(self.uuid)

      self.model.create_citation(root = crs, title = title, originator = originator)

      xoffset = rqet.SubElement(crs, ns['resqml2'] + 'XOffset')
      xoffset.set(ns['xsi'] + 'type', ns['xsd'] + 'double')
      xoffset.text = '{0:5.3f}'.format(self.x_offset)

      yoffset = rqet.SubElement(crs, ns['resqml2'] + 'YOffset')
      yoffset.set(ns['xsi'] + 'type', ns['xsd'] + 'double')
      yoffset.text = '{0:5.3f}'.format(self.y_offset)

      zoffset = rqet.SubElement(crs, ns['resqml2'] + 'ZOffset')
      zoffset.set(ns['xsi'] + 'type', ns['xsd'] + 'double')
      zoffset.text = '{0:6.4f}'.format(self.z_offset)

      rotation = rqet.SubElement(crs, ns['resqml2'] + 'ArealRotation')
      rotation.set('uom', 'rad')
      rotation.set(ns['xsi'] + 'type', ns['eml'] + 'PlaneAngleMeasure')
      rotation.text = '{0:8.6f}'.format(self.rotation)

      if self.axis_order is None: axes = 'easting northing'
      else: axes = self.axis_order.lower()
      axis_order = rqet.SubElement(crs, ns['resqml2'] + 'ProjectedAxisOrder')
      axis_order.set(ns['xsi'] + 'type', ns['eml'] + 'AxisOrder2d')
      axis_order.text = axes

      xy_uom = rqet.SubElement(crs, ns['resqml2'] + 'ProjectedUom')
      xy_uom.set(ns['xsi'] + 'type', ns['eml'] + 'LengthUom')
      xy_uom.text = wam.rq_length_unit(self.xy_units)

      z_uom = rqet.SubElement(crs, ns['resqml2'] + 'VerticalUom')
      z_uom.set(ns['xsi'] + 'type', ns['eml'] + 'LengthUom')
      z_uom.text = wam.rq_length_unit(self.z_units)

      if self.time_units is not None:
         t_uom = rqet.SubElement(crs, ns['resqml2'] + 'TimeUom')
         t_uom.set(ns['xsi'] + 'type', ns['eml'] + 'TimeUom')  # todo: check this
         t_uom.text = self.time_units

      z_sense = rqet.SubElement(crs, ns['resqml2'] + 'ZIncreasingDownward')
      z_sense.set(ns['xsi'] + 'type', ns['xsd'] + 'boolean')
      z_sense.text = str(self.z_inc_down).lower()

      xy_crs = rqet.SubElement(crs, ns['resqml2'] + 'ProjectedCrs')
      xy_crs.text = rqet.null_xml_text
      if self.epsg_code is None:
         xy_crs.set(ns['xsi'] + 'type', ns['eml'] + 'ProjectedUnknownCrs')
         self.model.create_unknown(root = xy_crs)
      else:
         xy_crs.set(ns['xsi'] + 'type', ns['eml'] + 'ProjectedCrsEpsgCode')
         epsg_node = rqet.SubElement(xy_crs, ns['resqml2'] + 'EpsgCode')
         epsg_node.set(ns['xsi'] + 'type', ns['xsd'] + 'positiveInteger')
         epsg_node.text = str(self.epsg_code)

      z_crs = rqet.SubElement(crs, ns['resqml2'] + 'VerticalCrs')
      if self.epsg_code is None:
         z_crs.set(ns['xsi'] + 'type', ns['eml'] + 'VerticalUnknownCrs')
         z_crs.text = rqet.null_xml_text
         self.model.create_unknown(root = z_crs)
      else:   # not sure if this is appropriate for the vertical crs
         z_crs.set(ns['xsi'] + 'type', ns['eml'] + 'VerticalCrsEpsgCode')
         epsg_node = rqet.SubElement(xy_crs, ns['resqml2'] + 'EpsgCode')
         epsg_node.set(ns['xsi'] + 'type', ns['xsd'] + 'positiveInteger')
         epsg_node.text = str(self.epsg_code)

      self.crs_root = crs

      if root is not None: root.append(crs)
      if add_as_part: self.model.add_part('obj_' + flavour, bu.uuid_from_string(crs.attrib['uuid']), crs)
      if self.model.crs_root is None: self.model.crs_root = crs  # mark's as 'main' (ie. first) crs for model

      return crs
