from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import CartItem, Product, Order, OrderItem
from .forms import RegisterForm, ProductForm
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.views.decorators.http import require_POST
from .forms import ProfileUpdateForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash



def home(request):
    return render(request, 'store/home.html')


def product_list(request):
    query = request.GET.get('q')
    category = request.GET.get('category')

    products = Product.objects.all()

    if query:
        products = products.filter(title__icontains=query)

    if category:
        products = products.filter(category=category)

    return render(request, 'store/product_list.html', {
        'products': products,
        'query': query,
        'selected_category': category,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'store/product_detail.html', {'product': product})


@login_required
def product_add(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            messages.success(request, "Product created successfully.")
            return redirect('product_list')
    else:
        form = ProductForm()
    return render(request, 'store/product_form.html', {'form': form})


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if product.seller != request.user:
        return redirect('product_list')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully.")
            return redirect('product_detail', pk=pk)
    else:
        form = ProductForm(instance=product)

    return render(request, 'store/product_form.html', {'form': form})


@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if product.seller == request.user:
        product.delete()
    return redirect('product_list')


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created! You can now log in.")
            return redirect('login')
    else:
        form = RegisterForm()
    return render(request, 'store/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect('login')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('product_list')
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, 'store/login.html')



def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('home')


@login_required
def my_products(request):
    query = request.GET.get('q')
    category = request.GET.get('category')

    product_list = Product.objects.filter(seller=request.user)

    if query:
        product_list = product_list.filter(title__icontains=query)

    if category:
        product_list = product_list.filter(category=category)

    paginator = Paginator(product_list, 6)
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)

    return render(request, 'store/my_products.html', {
        'products': products,
        'query': query,
        'category': category,
    })


@login_required
def dashboard(request):
    user = request.user
    products = Product.objects.filter(seller=user)
    total_products = products.count()

    category_summary = products.values('category').annotate(count=Count('id')).order_by('-count')
    recent_products = products.order_by('-created_at')[:5]

    return render(request, 'store/dashboard.html', {
        'user': user,
        'total_products': total_products,
        'category_summary': category_summary,
        'recent_products': recent_products,
    })


@login_required
def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    quantity = int(request.POST.get('quantity', 1))

    cart_item, created = CartItem.objects.get_or_create(user=request.user, product=product)

    if not created:
        cart_item.quantity += quantity
    else:
        cart_item.quantity = quantity

    cart_item.save()
    messages.success(request, f"{product.title} added to cart.")
    return redirect('cart')


@login_required
def remove_from_cart(request, pk):
    cart_item = get_object_or_404(CartItem, pk=pk, user=request.user)
    cart_item.delete()
    messages.success(request, "Item removed from cart.")
    return redirect('cart')


@login_required
def cart_view(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total = sum(item.total_price for item in cart_items)

    if request.method == 'POST':
        for item in cart_items:
            item.delete()
        messages.success(request, "Checkout successful! Your order has been placed.")
        return redirect('product_list')

    return render(request, 'store/cart.html', {
        'cart_items': cart_items,
        'total': total
    })


@login_required
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total = sum(item.total_price for item in cart_items)

    if request.method == 'POST':
        address = request.POST.get('address', '').strip()
        note = request.POST.get('note', '').strip()

        if not address:
            messages.error(request, "Please provide your shipping address.")
            return render(request, 'store/checkout.html', {
                'cart_items': cart_items,
                'total': total
            })

        order = Order.objects.create(user=request.user, address=address, note=note)

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity
            )
            item.delete()

        messages.success(request, "Your order was placed successfully!")
        return redirect('order_success')

    return render(request, 'store/checkout.html', {
        'cart_items': cart_items,
        'total': total
    })


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'store/order_history.html', {'orders': orders})


@login_required
@require_POST
def update_cart_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, user=request.user)
    try:
        new_quantity = int(request.POST.get('quantity', 1))
        if new_quantity > 0:
            item.quantity = new_quantity
            item.save()
            messages.success(request, f"Updated quantity for {item.product.title}.")
        else:
            item.delete()
            messages.warning(request, f"Removed {item.product.title} from cart.")
    except ValueError:
        messages.error(request, "Invalid quantity value.")
    return redirect('cart')


@login_required
def update_cart(request):
    if request.method == "POST":
        for key, value in request.POST.items():
            if key.startswith("quantity_"):
                try:
                    item_id = int(key.split("_")[1])
                    quantity = int(value)
                    item = get_object_or_404(CartItem, pk=item_id, user=request.user)

                    if quantity > 0:
                        item.quantity = quantity
                        item.save()
                    else:
                        item.delete()
                except Exception as e:
                    print(f"Error updating item {key}: {e}")
    return redirect('cart')


@login_required
def profile(request):
    return render(request, 'store/profile.html')


@login_required
def order_success(request):
    return render(request, 'store/order_success.html')

@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(request, 'store/profile.html', {
        'form': form
    })

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  
            messages.success(request, "Password changed successfully.")
            return redirect('profile')
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, 'store/password_change.html', {'form': form})