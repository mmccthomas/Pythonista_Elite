from dataclasses import dataclass, field
from math import sqrt
import numpy as np
NOSEV = 2
ROOFV = 1
SIDEV = 0


def mult_matrix(first, second):

    rv = Matrix()
    for i in range(3):
   
        rv[i].x = ((first[0].x * second[i].x)
                   + (first[1].x * second[i].y)
                   + (first[2].x * second[i].z))
     
        rv[i].y = ((first[0].y * second[i].x)
                   + (first[1].y * second[i].y)
                   + (first[2].y * second[i].z))
     
        rv[i].z = ((first[0].z * second[i].x)
                   + (first[1].z * second[i].y)
                   + (first[2].z * second[i].z))
           
    for i in range(3):
        first[i] = rv[i]
          

def mult_vector(vec, mat):
    
    x = ((vec.x * mat[SIDEV].x)
         + (vec.y * mat[SIDEV].y)
         + (vec.z * mat[SIDEV].z))
  
    y = ((vec.x * mat[ROOFV].x)
         + (vec.y * mat[ROOFV].y)
         + (vec.z * mat[ROOFV].z))
  
    z = ((vec.x * mat[NOSEV].x)
         + (vec.y * mat[NOSEV].y)
         + (vec.z * mat[NOSEV].z))
  
    vec.x, vec.y, vec.z = x, y, z


def vector_dot_product(A, B):
    """
    Returns the scalar dot product of two vectors.
    """
    return A.x * B.x + A.y * B.y + A.z * B.z


def unit_vector(vec):
    res = Vector()
    lx, ly, lz = vec.x, vec.y, vec.z
  
    uni = sqrt(lx * lx + ly * ly + lz * lz)
    try:
        res.x = lx / uni
        res.y = ly / uni
        res.z = lz / uni
        
    except ZeroDivisionError:
        res = Vector(0.0, 0.0, 0.0)
    return res


def set_init_matrix():
    # Static start matrix (The initial orientation of the ship)
    # Note: Z is -1.0 to reflect the original Elite coordinate system
    return [Vector(1.0, 0.0, 0.0),
            Vector(0.0, 1.0, 0.0),
            Vector(0.0, 0.0, -1.0)]


def tidy_matrix(mat):
    """
    Ensures the matrix remains orthogonal (axes at 90 degrees) and normalized.
    This prevents floating-point drift from 'warping' the ships over time.
    """
    try:
        # 1. Normalize the Z-axis (Forward vector)
        mat[NOSEV] = unit_vector(mat[NOSEV])
        # 2. Re-calculate Y-axis to be orthogonal to Z
        # (Gram-Schmidt process logic from the original C code)
        if ((mat[NOSEV].x > -1) and (mat[NOSEV].x < 1)):
            if ((mat[NOSEV].y > -1) and (mat[NOSEV].y < 1)):
                mat[ROOFV].z = -(mat[NOSEV].x * mat[ROOFV].x + mat[NOSEV].y * mat[ROOFV].y) / mat[NOSEV].z
            else:
                mat[ROOFV].y = -(mat[NOSEV].x * mat[ROOFV].x + mat[NOSEV].z * mat[ROOFV].z) / mat[NOSEV].y
        else:
            mat[ROOFV].x = -(mat[NOSEV].y * mat[ROOFV].y + mat[NOSEV].z * mat[ROOFV].z) / mat[NOSEV].x
            
        mat[ROOFV] = unit_vector(mat[ROOFV])
            
        # 3. Calculate X-axis using the Cross Product of Y and Z
        # xyzzy... nothing happens. :-)
        
        mat[SIDEV].x = mat[ROOFV].y * mat[NOSEV].z - mat[ROOFV].z * mat[NOSEV].y
        mat[SIDEV].y = mat[ROOFV].z * mat[NOSEV].x - mat[ROOFV].x * mat[NOSEV].z
        mat[SIDEV].z = mat[ROOFV].x * mat[NOSEV].y - mat[ROOFV].y * mat[NOSEV].x
        
    except ZeroDivisionError:
       pass

            
@dataclass
class Vector:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    
    def to_np(self):
        return np.array([self.x, self.y, self.z])
        
    @property
    def to_tuple(self):
        return (self.x, self.y, self.z)
        
    # ── addition ──────────────────────────────────────────────────────────────

    def __add__(self, other):
        if isinstance(other, Vector):
            return Vector(self.x + other.x, self.y + other.y, self.z + other.z)
        return Vector(self.x + other, self.y + other, self.z + other)

    def __radd__(self, other):
        return Vector(other + self.x, other + self.y, other + self.z)

    # ── subtraction ───────────────────────────────────────────────────────────

    def __sub__(self, other):
        if isinstance(other, Vector):
            return Vector(self.x - other.x, self.y - other.y, self.z - other.z)
        return Vector(self.x - other, self.y - other, self.z - other)

    def __rsub__(self, other):
        return Vector(other - self.x, other - self.y, other - self.z)
        
    # ── multiplication ────────────────────────────────────────────────────────

    def __mul__(self, other):
        if isinstance(other, Vector):
            return Vector(self.x * other.x, self.y * other.y, self.z * other.z)
        return Vector(self.x * other, self.y * other, self.z * other)

    def __rmul__(self, other):
        return Vector(other * self.x, other * self.y, other * self.z)

    # ── division (true) ───────────────────────────────────────────────────────

    def __truediv__(self, other):
        if isinstance(other, Vector):
            return Vector(self.x / other.x, self.y / other.y, self.z / other.z)
        return Vector(self.x / other, self.y / other, self.z / other)

    def __rtruediv__(self, other):
        return Vector(other / self.x, other / self.y, other / self.z)

    # ── floor division ────────────────────────────────────────────────────────

    def __floordiv__(self, other):
        if isinstance(other, Vector):
            return Vector(int(self.x // other.x), int(self.y // other.y), int(self.z // other.z))
        return Vector(int(self.x // other), int(self.y // other), int(self.z // other))

    def __rfloordiv__(self, other):
        return Vector(int(other // self.x), int(other // self.y), int(other // self.z))
        
    # ── in-place operators ────────────────────────────────────────────────────

    def __iadd__(self, other): return self.__add__(other)
    def __isub__(self, other): return self.__sub__(other)
    def __imul__(self, other): return self.__mul__(other)
    def __itruediv__(self, other): return self.__truediv__(other)
    def __ifloordiv__(self, other): return self.__floordiv__(other)
    # def __imod__(self, other):      return self.__mod__(other)
       
    @property
    def magnitude(self):
        a = self.x * self.x
        b = self.y * self.y
        c = self.z * self.z
        return sqrt(a+b+c)

                
@dataclass
class Matrix:
    rotmat: list = field(default_factory=lambda: [Vector(), Vector(), Vector()])

    def __getitem__(self, index):
        return self.rotmat[index]

            
if __name__ == '__main__':
   mat = [Vector(-1, -.05,  .002), Vector(-.051, 1, -.05), Vector(0, -.05, -1)]
   mat1 = tidy_matrix(mat)
   val = vector_dot_product(Vector(-1, -.05,  .002), Vector(-.051, 1, -.05))
   print(val)
 


