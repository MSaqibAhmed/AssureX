from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import EmailStr, Field
from src.schemas.evaluation import StrictModel

class Login(StrictModel):
    email: EmailStr
    password: str = Field(min_length=8,max_length=128)
class Register(Login):
    name: str = Field(min_length=1,max_length=100)
class Product(StrictModel):
    name: str = Field(default='',max_length=150)
    retailer: str = Field(default='',max_length=150)
    serial: str = Field(min_length=2,max_length=100)
    brand: str = Field(min_length=1,max_length=100)
    model: str = Field(min_length=1,max_length=100)
    category: Literal['mobile','electronics','appliances']
    purchase_date: date
    amount: Decimal = Field(ge=0,max_digits=12,decimal_places=2)
class Warranty(StrictModel):
    provider: str = Field(min_length=1,max_length=100)
    start_date: date
    expiry_date: date
    policy_version_id: str
class Facts(StrictModel):
    fault_date: date | None = None
    fault_category: str | None = Field(default=None,max_length=100)
    description: str = Field(default='',max_length=4000)
    damage_type: str | None = Field(default=None,max_length=100)
    serial: str | None = Field(default=None,max_length=100)
    invoice_number: str | None = Field(default=None,max_length=100)
class ClaimCreate(StrictModel):
    product_id: str
    facts: Facts
class ClaimPatch(StrictModel):
    version: int = Field(ge=1)
    status: str
    facts: Facts | None = None
    target_status: Literal['Closed'] | None = None
class Expected(StrictModel):
    version: int = Field(ge=1)
    status: str
class Review(Expected):
    action: Literal['approve','reject','request_info']
    reason: str = Field(min_length=1,max_length=4000,pattern=r'\S')
    evaluation_id: str
class Comment(StrictModel):
    message: str = Field(min_length=1,max_length=4000,pattern=r'\S')
    visibility: Literal['customer','staff'] = 'customer'
class Correction(StrictModel):
    normalized_value: str = Field(min_length=1,max_length=200)
class ReadNotice(StrictModel):
    read: bool = True
class Repair(StrictModel):
    parts: str = Field(default='',max_length=1000)
    outcome: str = Field(default='',max_length=1000)
    cost: Decimal = Field(default=0,ge=0,max_digits=12,decimal_places=2)
    claim_id: str
    date: date
    authorized: bool | None
    notes: str = Field(min_length=1,max_length=4000)
class Replacement(Repair):
    old_serial: str
    new_serial: str
class Activation(StrictModel):
    model_version_id: str
    reason: str = Field(min_length=1,max_length=1000,pattern=r'\S')

class ProfileUpdate(StrictModel):
    name: str = Field(min_length=1,max_length=100,pattern=r'\S')
    phone: str = Field(default='',max_length=40)

class UserCreate(Register):
    role: Literal['customer','service','reviewer','admin']
    center_id: str | None = None

class UserAccess(StrictModel):
    active: bool

class Assignment(StrictModel):
    version: int = Field(ge=1)
    status: str
    reviewer_id: str
