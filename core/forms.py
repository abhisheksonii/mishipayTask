from django import forms
from .models import Product, Supplier, SaleOrder, StockMovement
from bson import ObjectId
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.core.exceptions import ValidationError

class ProductForm(forms.ModelForm):
    supplier = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'price', 'stock_quantity', 'supplier']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control'}),
            'category': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        suppliers = Supplier.objects.all()
        self.fields['supplier'].choices = [('', 'Select a Supplier')] + [
            (str(s._id), s.name) for s in suppliers
        ]

    def clean(self):
        cleaned_data = super().clean()
        supplier_id = self.cleaned_data.get('supplier')
        
        if supplier_id:
            try:
                supplier = Supplier.objects.get(_id=ObjectId(supplier_id))
                cleaned_data['supplier'] = supplier
            except Exception as e:
                print(f"Error finding supplier: {e}")
                raise forms.ValidationError("Invalid supplier selected")
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        supplier_id = self.cleaned_data.get('supplier')
        if supplier_id:
            instance.supplier = supplier_id
        if commit:
            instance.save()
        return instance

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'email', 'phone', 'address']

class SaleOrderForm(forms.ModelForm):
    product = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1'})
    )

    class Meta:
        model = SaleOrder
        fields = ['product', 'quantity']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show products with stock > 0
        products = Product.objects.filter(stock_quantity__gt=0)
        if products.exists():
            self.fields['product'].choices = [('', '-- Select a Product --')] + [
                (str(p._id), f"{p.name} (Stock: {p.stock_quantity}, Price: ${float(p.price):.2f})") 
                for p in products
            ]
        else:
            self.fields['product'].choices = [('', 'No products available')]
            self.fields['product'].widget.attrs['disabled'] = True
            self.fields['quantity'].widget.attrs['disabled'] = True

    def clean_product(self):
        product_id = self.cleaned_data.get('product')
        if not product_id:
            raise forms.ValidationError("Please select a product")
        
        try:
            product = Product.objects.get(_id=ObjectId(product_id))
            if product.stock_quantity <= 0:
                raise forms.ValidationError(f"{product.name} is out of stock")
            return product
        except (Product.DoesNotExist, InvalidOperation) as e:
            print(f"Error finding product: {e}")
            raise forms.ValidationError("Invalid product selected")

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is None:
            raise forms.ValidationError("Please enter a quantity")
        if quantity < 1:
            raise forms.ValidationError("Quantity must be at least 1")
        
        product_id = self.data.get('product')
        if product_id:
            try:
                product = Product.objects.get(_id=ObjectId(product_id))
                if quantity > product.stock_quantity:
                    raise forms.ValidationError(
                        f'Only {product.stock_quantity} units available for {product.name}'
                    )
            except (Product.DoesNotExist, InvalidOperation):
                pass  # Product validation will be handled by clean_product
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        
        if product and quantity:
            try:
                # Convert price to Decimal explicitly
                price = Decimal(str(product.price))
                quantity_decimal = Decimal(str(quantity))
                total_price = price * quantity_decimal
                # Round to 2 decimal places
                cleaned_data['total_price'] = Decimal(str(round(total_price, 2)))
            except (TypeError, ValueError, InvalidOperation) as e:
                print(f"Error calculating total price: {e}")
                raise forms.ValidationError("Error calculating total price")
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        product = self.cleaned_data.get('product')
        quantity = self.cleaned_data.get('quantity')
        total_price = self.cleaned_data.get('total_price')
        
        if product and quantity and total_price:
            instance.product = product
            instance.quantity = quantity
            instance.total_price = total_price
            
            if commit:
                try:
                    with transaction.atomic():
                        # Final stock check
                        if quantity > product.stock_quantity:
                            raise forms.ValidationError(
                                f'Only {product.stock_quantity} units available for {product.name}'
                            )
                        instance.save()
                        # Update product stock
                        product.stock_quantity -= quantity
                        product.save()
                except Exception as e:
                    print(f"Error saving sale order: {e}")
                    raise forms.ValidationError(f"Error saving sale order: {str(e)}")
                
        return instance

class StockMovementForm(forms.ModelForm):
    product = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1'})
    )
    movement_type = forms.ChoiceField(
        choices=StockMovement.MOVEMENT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )

    class Meta:
        model = StockMovement
        fields = ['product', 'quantity', 'movement_type', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get all products
        products = Product.objects.all()
        if products.exists():
            self.fields['product'].choices = [('', '-- Select a Product --')] + [
                (str(p._id), f"{p.name} (Current Stock: {p.stock_quantity})") 
                for p in products
            ]
        else:
            self.fields['product'].choices = [('', 'No products available')]
            self.fields['product'].widget.attrs['disabled'] = True
            self.fields['quantity'].widget.attrs['disabled'] = True

    def clean_product(self):
        product_id = self.cleaned_data.get('product')
        if not product_id:
            raise forms.ValidationError("Please select a product")
        
        try:
            return Product.objects.get(_id=ObjectId(product_id))
        except (Product.DoesNotExist, InvalidOperation) as e:
            print(f"Error finding product: {e}")
            raise forms.ValidationError("Invalid product selected")

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is None:
            raise forms.ValidationError("Please enter a quantity")
        if quantity < 1:
            raise forms.ValidationError("Quantity must be at least 1")
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        movement_type = cleaned_data.get('movement_type')

        if product and quantity and movement_type:
            if movement_type == 'Out':
                if quantity > product.stock_quantity:
                    raise forms.ValidationError(
                        f'Only {product.stock_quantity} units available for {product.name}'
                    )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        product = self.cleaned_data.get('product')
        quantity = self.cleaned_data.get('quantity')
        movement_type = self.cleaned_data.get('movement_type')
        
        if product and quantity and movement_type:
            instance.product = product
            
            if commit:
                try:
                    with transaction.atomic():
                        # Final stock check for 'Out' movements
                        if movement_type == 'Out' and quantity > product.stock_quantity:
                            raise forms.ValidationError(
                                f'Only {product.stock_quantity} units available for {product.name}'
                            )
                        instance.save()
                        
                        # Update product stock
                        if movement_type == 'In':
                            product.stock_quantity += quantity
                        else:  # Out
                            product.stock_quantity -= quantity
                        product.save()
                except Exception as e:
                    print(f"Error saving stock movement: {e}")
                    raise forms.ValidationError(f"Error saving stock movement: {str(e)}")
                
        return instance 