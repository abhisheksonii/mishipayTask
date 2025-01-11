from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import F
from .models import Product, Supplier, SaleOrder, StockMovement
from .forms import ProductForm, SupplierForm, SaleOrderForm, StockMovementForm
from .auth_forms import RegistrationForm
from bson.objectid import ObjectId
from django.db import transaction
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login

def landing_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html')

def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RegistrationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def dashboard(request):
    products = Product.objects.select_related('supplier').all()
    return render(request, 'products/list.html', {'products': products})

@login_required
def product_list(request):
    products = Product.objects.select_related('supplier').all()
    return render(request, 'products/list.html', {'products': products})

@login_required
def add_product(request):
    suppliers = Supplier.objects.all()
    print(f"Available suppliers in view: {[{'id': s.id, 'name': s.name} for s in suppliers]}")
    
    if not suppliers.exists():
        messages.error(request, 'Please add a supplier before adding products')
        return redirect('add_supplier')
    
    if request.method == 'POST':
        print(f"POST data: {request.POST}")
        form = ProductForm(request.POST)
        
        try:
            if form.is_valid():
                product = form.save()
                messages.success(request, f'Product "{product.name}" added successfully')
                return redirect('product_list')
            else:
                print(f"Form errors: {form.errors}")
                messages.error(request, 'Please correct the errors below')
        except Exception as e:
            print(f"Exception: {str(e)}")
            messages.error(request, f'Error adding product: {str(e)}')
    else:
        form = ProductForm()
    
    return render(request, 'products/add.html', {
        'form': form,
        'suppliers': suppliers
    })

@login_required
def supplier_list(request):
    suppliers = Supplier.objects.all()
    return render(request, 'suppliers/list.html', {'suppliers': suppliers})

@login_required
def add_supplier(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplier added successfully!')
            return redirect('supplier_list')
    else:
        form = SupplierForm()
    return render(request, 'suppliers/add.html', {'form': form})

@login_required
def add_stock_movement(request):
    if request.method == 'POST':
        form = StockMovementForm(request.POST)
        try:
            if form.is_valid():
                with transaction.atomic():
                    movement = form.save()
                    messages.success(
                        request, 
                        f'Stock movement recorded successfully! {movement.quantity} units {"added to" if movement.movement_type == "In" else "removed from"} {movement.product.name}'
                    )
                    return redirect('check_stock_levels')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error recording stock movement: {str(e)}')
    else:
        form = StockMovementForm()
    
    # Check if there are any products
    products_exist = Product.objects.exists()
    if not products_exist:
        messages.warning(request, 'Please add products before recording stock movements')
    
    return render(request, 'stock/movement.html', {
        'form': form,
        'products_exist': products_exist
    })

@login_required
def create_sale_order(request):
    # Check if there are any products with stock
    if not Product.objects.filter(stock_quantity__gt=0).exists():
        messages.error(request, 'No products available for sale')
        return redirect('product_list')

    if request.method == 'POST':
        form = SaleOrderForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    product = form.cleaned_data['product']
                    quantity = form.cleaned_data['quantity']
                    
                    # Recheck stock one final time before saving
                    if quantity > product.stock_quantity:
                        messages.error(request, f'Only {product.stock_quantity} units available for {product.name}')
                        return redirect('create_sale_order')
                    
                    sale_order = form.save()
                    
                    # Update product stock
                    product.stock_quantity -= quantity
                    product.save()
                    
                    messages.success(request, 'Sale order created successfully!')
                    return redirect('sale_order_list')
            except Exception as e:
                messages.error(request, f'Error creating sale order: {str(e)}')
                return redirect('create_sale_order')
    else:
        form = SaleOrderForm()
    
    return render(request, 'sales/create.html', {'form': form})

def cancel_sale_order(request, order_id):
    try:
        with transaction.atomic():
            sale_order = get_object_or_404(SaleOrder, _id=ObjectId(order_id))
            
            # Only allow cancellation of pending orders
            if sale_order.status != 'pending':
                messages.error(request, 'Only pending orders can be cancelled')
                return redirect('sale_order_list')
            
            # Convert total_price to Decimal
            if not isinstance(sale_order.total_price, Decimal):
                sale_order.total_price = Decimal(str(sale_order.total_price))
            
            # First update the product stock
            product = sale_order.product
            product.stock_quantity += sale_order.quantity
            product.full_clean()
            product.save()
            
            # Then update the sale order status
            sale_order.status = 'cancelled'
            sale_order.save()
            
            messages.success(request, f'Sale order for {sale_order.quantity} units of {product.name} cancelled successfully!')
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Error cancelling order: {str(e)}')
    return redirect('sale_order_list')

def complete_sale_order(request, order_id):
    try:
        with transaction.atomic():
            sale_order = get_object_or_404(SaleOrder, _id=ObjectId(order_id))
            
            # Only allow completion of pending orders
            if sale_order.status != 'pending':
                messages.error(request, 'Only pending orders can be completed')
                return redirect('sale_order_list')
            
            # Convert total_price to Decimal
            if not isinstance(sale_order.total_price, Decimal):
                sale_order.total_price = Decimal(str(sale_order.total_price))
            
            # Verify stock availability one last time
            if sale_order.quantity > sale_order.product.stock_quantity:
                messages.error(request, f'Insufficient stock available for {sale_order.product.name}')
                return redirect('sale_order_list')
            
            # Update the order status
            sale_order.status = 'completed'
            sale_order.save()
            
            messages.success(request, f'Sale order for {sale_order.quantity} units of {sale_order.product.name} completed successfully!')
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Error completing order: {str(e)}')
    return redirect('sale_order_list')

@login_required
def sale_order_list(request):
    sale_orders = SaleOrder.objects.select_related('product').all()
    products_available = Product.objects.filter(stock_quantity__gt=0).exists()
    return render(request, 'sales/list.html', {
        'sale_orders': sale_orders,
        'products_available': products_available
    })

@login_required
def check_stock_levels(request):
    stock_movements = StockMovement.objects.select_related('product', 'product__supplier').all()
    return render(request, 'stock/levels.html', {'stock_movements': stock_movements})

@login_required
def delete_product(request, product_id):
    try:
        product = get_object_or_404(Product, _id=ObjectId(product_id))
        name = product.name
        product.delete()
        messages.success(request, f'Product "{name}" deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting product: {str(e)}')
    return redirect('product_list')

@login_required
def delete_supplier(request, supplier_id):
    try:
        supplier = get_object_or_404(Supplier, _id=ObjectId(supplier_id))
        # Check if supplier has associated products
        if Product.objects.filter(supplier=supplier).exists():
            messages.error(request, 'Cannot delete supplier with associated products')
            return redirect('supplier_list')
        
        name = supplier.name
        supplier.delete()
        messages.success(request, f'Supplier "{name}" deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting supplier: {str(e)}')
    return redirect('supplier_list')

@login_required
def delete_sale_order(request, order_id):
    try:
        order = get_object_or_404(SaleOrder, _id=ObjectId(order_id))
        if order.status != 'pending':
            messages.error(request, 'Only pending orders can be deleted')
            return redirect('sale_order_list')
        
        # Return stock to product
        product = order.product
        product.stock_quantity += order.quantity
        product.save()
        
        order.delete()
        messages.success(request, 'Sale order deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting sale order: {str(e)}')
    return redirect('sale_order_list')

@login_required
def delete_stock_movement(request, movement_id):
    try:
        movement = get_object_or_404(StockMovement, _id=ObjectId(movement_id))
        movement.delete()
        messages.success(request, 'Stock movement deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting stock movement: {str(e)}')
    return redirect('check_stock_levels')

@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, _id=ObjectId(product_id))
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f'Product "{product.name}" updated successfully')
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'products/edit.html', {'form': form, 'product': product})

@login_required
def edit_supplier(request, supplier_id):
    supplier = get_object_or_404(Supplier, _id=ObjectId(supplier_id))
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, f'Supplier "{supplier.name}" updated successfully')
            return redirect('supplier_list')
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'suppliers/edit.html', {'form': form, 'supplier': supplier}) 