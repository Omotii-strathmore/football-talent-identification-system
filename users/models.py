from django.db import models


class UserManager(BaseUserManager):
   def create_user(self, email, password=None, role='player' ):

       if not email:
            raise ValueError('Users must have an email address')

       user = self.model(
           email=email
           role=role
       )
       user.set_password(password)
       user.save(using=self._db)
     
       return user


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)

ROLE_CHOICES =[
        ('player','Player'),
        ('scout', 'Scout'),
        ('admin', 'Admin'),
    ]

role = models.CharField(max_length=20, choices=ROLE_CHOICES)
is_active = models.BooleanField(default=True)
is_staff = models.BooleanField(default=False)


USERNAME_FIELD = 'email'
objects = UserManager()

def __str__(self):
    return self.email