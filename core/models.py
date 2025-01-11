from djongo import models
from django.core.validators import MinValueValidator, RegexValidator
from .validators import validate_phone_number, validate_email
from django.core.exceptions import ValidationError
from bson import ObjectId
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

class Supplier(models.Model):
    _id = models.ObjectIdField(primary_key=True, default=ObjectId)
    name = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True, validators=[validate_email])
    phone = models.CharField(
        max_length=10,
        validators=[validate_phone_number],
        unique=True
    )
    address = models.TextField()

    def __str__(self):
        return self.name

    @property
    def id(self):
        return str(self._id)

class Product(models.Model):
    _id = models.ObjectIdField(primary_key=True, default=ObjectId)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    category = models.CharField(max_length=50)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    stock_quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)

    def clean(self):
        if self.stock_quantity < 0:
            raise ValidationError('Stock quantity cannot be negative')
        if self.price < Decimal('0.01'):
            raise ValidationError('Price must be at least 0.01')
        try:
            self.price = Decimal(str(self.price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except (TypeError, ValueError, InvalidOperation):
            raise ValidationError('Invalid price value')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def id(self):
        return str(self._id)

    @property
    def formatted_price(self):
        return Decimal(str(self.price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

class SaleOrder(models.Model):
    _id = models.ObjectIdField(primary_key=True, default=ObjectId)
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_date = models.DateField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending'
    )

    def calculate_total_price(self):
        """Calculate total price from product price and quantity"""
        if self.product and self.quantity:
            try:
                price = Decimal(str(self.product.price))
                quantity = Decimal(str(self.quantity))
                return (price * quantity).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            except (TypeError, ValueError, InvalidOperation) as e:
                raise ValidationError(f'Error calculating total price: {str(e)}')
        return Decimal('0.00')

    def clean(self):
        super().clean()
        # Validate quantity
        if self.quantity and self.quantity < 1:
            raise ValidationError('Quantity must be at least 1')
        
        # Validate product stock
        if self.product and self.quantity:
            if self.status == 'pending':
                product_stock = self.product.stock_quantity
                if isinstance(product_stock, str):
                    product_stock = int(product_stock)
                if self.quantity > product_stock:
                    raise ValidationError(f'Only {product_stock} units available')

        # Convert and validate total price
        try:
            if hasattr(self.total_price, 'to_decimal'):
                # Handle Decimal128
                self.total_price = Decimal(str(self.total_price.to_decimal()))
            elif not isinstance(self.total_price, Decimal):
                self.total_price = Decimal(str(self.total_price))
            self.total_price = self.total_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except (TypeError, ValueError, InvalidOperation, AttributeError) as e:
            raise ValidationError(f'Error with total price: {str(e)}')

    def save(self, *args, **kwargs):
        # Convert total_price to Decimal
        try:
            if hasattr(self.total_price, 'to_decimal'):
                # Handle Decimal128
                self.total_price = Decimal(str(self.total_price.to_decimal()))
            elif not isinstance(self.total_price, Decimal):
                self.total_price = Decimal(str(self.total_price))
            self.total_price = self.total_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except (TypeError, ValueError, InvalidOperation, AttributeError) as e:
            raise ValidationError(f'Error with total price: {str(e)}')
        
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Convert total_price to Decimal before deletion
        try:
            if hasattr(self.total_price, 'to_decimal'):
                # Handle Decimal128
                self.total_price = Decimal(str(self.total_price.to_decimal()))
            elif not isinstance(self.total_price, Decimal):
                self.total_price = Decimal(str(self.total_price))
        except (TypeError, ValueError, InvalidOperation, AttributeError) as e:
            print(f"Warning: Error converting total_price during deletion: {str(e)}")
        super().delete(*args, **kwargs)

    @property
    def id(self):
        return str(self._id)

    @property
    def formatted_total_price(self):
        try:
            if hasattr(self.total_price, 'to_decimal'):
                # Handle Decimal128
                decimal_value = Decimal(str(self.total_price.to_decimal()))
            elif not isinstance(self.total_price, Decimal):
                decimal_value = Decimal(str(self.total_price))
            else:
                decimal_value = self.total_price
            return decimal_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except (TypeError, ValueError, InvalidOperation, AttributeError) as e:
            print(f"Warning: Error formatting total price: {str(e)}")
            return Decimal('0.00')

class StockMovement(models.Model):
    MOVEMENT_CHOICES = [
        ('In', 'In'),
        ('Out', 'Out'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    movement_type = models.CharField(max_length=3, choices=MOVEMENT_CHOICES)
    movement_date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def clean(self):
        super().clean()
        if self.quantity < 1:
            raise ValidationError('Quantity must be at least 1')
        if self.movement_type == 'Out' and self.product and self.quantity > self.product.stock_quantity:
            raise ValidationError('Insufficient stock available for this movement') 