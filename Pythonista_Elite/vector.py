from dataclasses import dataclass, field
from  math import sqrt

def mult_matrix(first, second):

    rv = Matrix()
    for i in range(3):    
   
        rv[i].x = ((first[0].x * second[i].x) +
              (first[1].x * second[i].y) +
              (first[2].x * second[i].z))
     
        rv[i].y = ((first[0].y * second[i].x) +
              (first[1].y * second[i].y) +
              (first[2].y * second[i].z))
     
        rv[i].z = ((first[0].z * second[i].x) +
              (first[1].z * second[i].y) +
              (first[2].z * second[i].z))
      
     
    for i in range(3):
        first[i] = rv[i]
          

def mult_vector (vec, mat):
    
      x = ((vec.x * mat[0].x) +
        (vec.y * mat[0].y) +
        (vec.z * mat[0].z))
    
      y = ((vec.x * mat[1].x) +
        (vec.y * mat[1].y) +
        (vec.z * mat[1].z))
    
      z = ((vec.x * mat[2].x) +
        (vec.y * mat[2].y) +
        (vec.z * mat[2].z))
    
      vec.x, vec.y, vec.z = x, y, z


def vector_dot_product(A, B):
    """
    Returns the scalar dot product of two vectors.
    """
    return A.x * B.x + A.y * B.y + A.z * B.z


def unit_vector(vec):  
      res = Vector()
      lx, ly, lz  = vec.x, vec.y, vec.z
    
      uni = sqrt(lx * lx + ly * ly + lz * lz);
    
      res.x = lx / uni
      res.y = ly / uni
      res.z = lz / uni      
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
    # 1. Normalize the Z-axis (Forward vector)
    mat[2] = unit_vector(mat[2])
    # 2. Re-calculate Y-axis to be orthogonal to Z
    # (Gram-Schmidt process logic from the original C code)
    if ((mat[2].x > -1) and (mat[2].x < 1)):
        if ((mat[2].y > -1) and (mat[2].y < 1)): 
              mat[1].z = -(mat[2].x * mat[1].x + mat[2].y * mat[1].y) / mat[2].z  
        else:        
              mat[1].y = -(mat[2].x * mat[1].x + mat[2].z * mat[1].z) / mat[2].y
    else:     
          mat[1].x = -(mat[2].y * mat[1].y + mat[2].z * mat[1].z) / mat[2].x;
        
    mat[1] = unit_vector(mat[1])  
        
    # 3. Calculate X-axis using the Cross Product of Y and Z
    # xyzzy... nothing happens. :-)    
    
    mat[0].x = mat[1].y * mat[2].z - mat[1].z * mat[2].y
    mat[0].y = mat[1].z * mat[2].x - mat[1].x * mat[2].z
    mat[0].z = mat[1].x * mat[2].y - mat[1].y * mat[2].x
        
      
@dataclass
class Vector:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    
    def to_np(self):
        return np.array([self.x, self.y, self.z])
        
    def to_tuple(self):
        return (self.x, self.y, self.z)
    # ── addition ──────────────────────────────────────────────────────────────

    def __add__(self, other):
        if isinstance(other, Vector):
            return Vector(self.x + other.x, self.y + other.y, self.z + other.z)
        return Point3(self.x + other, self.y + other, self.z + other)

    def __radd__(self, other):
        return Vector(other + self.x, other + self.y, other + self.z)

    # ── subtraction ───────────────────────────────────────────────────────────

    def __sub__(self, other):
        if isinstance(other, Vector):
            return Vector(self.x - other.x, self.y - other.y, self.z - other.z)
        return Vector(self.x - other, self.y - other, self.z - other)

    def __rsub__(self, other):
        return Vector(other - self.x, other - self.y, other - self.z)
        
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
 


