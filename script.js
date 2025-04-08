// Sample product data
const products = [
  {
    id: 1,
    name: "Christ in Gethsemane",
    description: "Powerful depiction of Christ's prayer in Gethsemane",
    price: 39.99,
    image: "assets/poster1.jpg",
  },
  {
    id: 2,
    name: "The First Vision",
    description: "Sacred moment of Joseph Smith's first vision",
    price: 39.99,
    image: "assets/poster2.jpg",
  },
  {
    id: 3,
    name: "The Living Christ",
    description: "Inspiring representation of the resurrected Christ",
    price: 39.99,
    image: "assets/poster3.jpg",
  },
  {
    id: 4,
    name: "The Restoration",
    description: "Symbolic representation of the Restoration",
    price: 39.99,
    image: "assets/poster4.jpg",
  },
  {
    id: 5,
    name: "The Plan of Salvation",
    description: "Beautiful visualization of God's plan",
    price: 39.99,
    image: "assets/poster5.jpg",
  }
]

// Cart functionality
let cart = []
const cartItems = document.getElementById("cart-items")
const cartTotal = document.getElementById("cart-total")
const cartCount = document.querySelector(".cart-count")
const cartSidebar = document.getElementById("cart-sidebar")
const overlay = document.getElementById("overlay")
const checkoutBtn = document.getElementById("checkout-btn")

// API Gateway URL (replace with your actual API Gateway URL after deployment)
const API_URL = "https://6ypk9kjze3.execute-api.us-west-2.amazonaws.com/prod"

// Initialize Stripe
let stripe
try {
  // Initialize Stripe with your publishable key
  stripe = Stripe('pk_live_51PbnbRRut3hoXCRuHV1jx7CxLFOUarhmGYpEqoAAechuMo3O6vSdhGzEj1XLogas2o9kKhRCYruCGCZ7pdkwU7m600cNO9Wq2l');
} catch (error) {
  console.error("Failed to initialize Stripe:", error)
}

// DOM Elements
const productsGrid = document.getElementById("products-grid")
const filterBtns = document.querySelectorAll(".filter-btn")
const cartToggle = document.getElementById("cart-toggle")
const closeCartBtn = document.getElementById("close-cart")
const productModal = document.getElementById("product-modal")
const closeModal = document.getElementById("close-modal")
const newsletterForm = document.getElementById("newsletter-form")
const contactLink = document.getElementById("contact-link")

// Display products
function displayProducts() {
  productsGrid.innerHTML = ""

  products.forEach((product) => {
    const productCard = document.createElement("div")
    productCard.classList.add("product-card")
    productCard.dataset.id = product.id

    productCard.innerHTML = `
      <div class="product-image">
        <img src="${product.image}" alt="${product.name}">
      </div>
      <div class="product-info">
        <h3>${product.name}</h3>
        <p>${product.description}</p>
        <div class="product-price">$${product.price.toFixed(2)}</div>
      </div>
    `

    productsGrid.appendChild(productCard)

    // Add click event to open modal
    productCard.addEventListener("click", () => {
      openProductModal(product)
    })
  })
}

// Filter products
filterBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    // Remove active class from all buttons
    filterBtns.forEach((btn) => btn.classList.remove("active"))

    // Add active class to clicked button
    btn.classList.add("active")

    // Get filter value
    const filter = btn.dataset.filter

    // Display filtered products
    displayProducts(filter)
  })
})

// Open product modal
function openProductModal(product) {
  const modalProduct = document.querySelector(".modal-product")

  modalProduct.innerHTML = `
    <div class="modal-product-image">
      <img src="${product.image}" alt="${product.name}">
    </div>
    <div class="modal-product-details">
      <h2 class="modal-product-title">${product.name}</h2>
      <p class="modal-product-description">${product.description}</p>
      <p class="modal-product-price">$${product.price.toFixed(2)}</p>
      <button class="btn primary-btn add-to-cart-btn" data-id="${product.id}">Add to Cart</button>
    </div>
  `

  // Add event listener to Add to Cart button
  const addToCartBtn = modalProduct.querySelector(".add-to-cart-btn")
  addToCartBtn.addEventListener("click", () => {
    addToCart(product)
    closeProductModal()
  })

  // Open modal
  productModal.classList.add("open")
  overlay.classList.add("open")
}

// Close product modal
function closeProductModal() {
  productModal.classList.remove("open")
  overlay.classList.remove("open")
}

// Add to cart
function addToCart(product) {
  // Check if product is already in cart
  const existingItem = cart.find((item) => item.id === product.id)

  if (existingItem) {
    // Increase quantity
    existingItem.quantity++
  } else {
    // Add new item
    cart.push({
      ...product,
      quantity: 1,
    })
  }

  // Update cart
  updateCart()

  // Open cart sidebar
  openCart()
}

// Update cart
function updateCart() {
  // Clear cart items
  cartItems.innerHTML = ""

  // Calculate total
  let total = 0
  let count = 0

  // Add items to cart
  cart.forEach((item) => {
    const cartItem = document.createElement("div")
    cartItem.classList.add("cart-item")

    cartItem.innerHTML = `
      <div class="cart-item-image">
        <img src="${item.image}" alt="${item.name}">
      </div>
      <div class="cart-item-details">
        <div class="cart-item-title">${item.name}</div>
        <div class="cart-item-price">$${item.price.toFixed(2)}</div>
        <div class="cart-item-quantity">
          <button class="quantity-btn decrease" data-id="${item.id}">-</button>
          <span>${item.quantity}</span>
          <button class="quantity-btn increase" data-id="${item.id}">+</button>
        </div>
        <button class="cart-item-remove" data-id="${item.id}">Remove</button>
      </div>
    `

    cartItems.appendChild(cartItem)

    // Add event listeners
    const decreaseBtn = cartItem.querySelector(".decrease")
    const increaseBtn = cartItem.querySelector(".increase")
    const removeBtn = cartItem.querySelector(".cart-item-remove")

    decreaseBtn.addEventListener("click", () => {
      decreaseQuantity(item.id)
    })

    increaseBtn.addEventListener("click", () => {
      increaseQuantity(item.id)
    })

    removeBtn.addEventListener("click", () => {
      removeFromCart(item.id)
    })

    // Update total and count
    total += item.price * item.quantity
    count += item.quantity
  })

  // Update cart total and count
  cartTotal.textContent = `$${total.toFixed(2)}`
  cartCount.textContent = count

  // Add email input if not already present
  let emailContainer = document.querySelector('.cart-email-container')
  if (!emailContainer && cart.length > 0) {
    emailContainer = document.createElement('div')
    emailContainer.classList.add('cart-email-container')
    emailContainer.innerHTML = `
      <label for="cart-email">Email for shipping updates:</label>
      <input type="email" id="cart-email" placeholder="Enter your email" required>
    `
    
    // Insert email container before cart footer
    const cartFooter = document.querySelector('.cart-footer')
    cartFooter.parentNode.insertBefore(emailContainer, cartFooter)
    
    // Enable/disable checkout button based on email validity
    const emailInput = emailContainer.querySelector('#cart-email')
    const checkoutBtn = document.getElementById('checkout-btn')
    
    emailInput.addEventListener('input', () => {
      const isValid = emailInput.checkValidity()
      checkoutBtn.disabled = !isValid
      emailInput.classList.toggle('error', !isValid)
    })
    
    // Initially disable checkout button
    checkoutBtn.disabled = true
  } else if (cart.length === 0 && emailContainer) {
    emailContainer.remove()
  }
}

// Decrease quantity
function decreaseQuantity(id) {
  const item = cart.find((item) => item.id === id)

  if (item.quantity > 1) {
    item.quantity--
  } else {
    removeFromCart(id)
  }

  updateCart()
}

// Increase quantity
function increaseQuantity(id) {
  const item = cart.find((item) => item.id === id)
  item.quantity++

  updateCart()
}

// Remove from cart
function removeFromCart(id) {
  cart = cart.filter((item) => item.id !== id)
  updateCart()
}

// Open cart
function openCart() {
  cartSidebar.classList.add("open")
  overlay.classList.add("open")
}

// Close cart
function closeCart() {
  cartSidebar.classList.remove("open")
  overlay.classList.remove("open")
}

// Handle newsletter form submission
newsletterForm.addEventListener("submit", (e) => {
  e.preventDefault()
  const email = newsletterForm.querySelector("input").value

  // Simulate API call
  console.log("Subscribing email:", email)

  // Show success message
  alert("Thank you for subscribing to our newsletter!")

  // Reset form
  newsletterForm.reset()
})

// Contact link
contactLink.addEventListener("click", (e) => {
  e.preventDefault()

  // Show contact info
  alert("Contact us at: info@steepledesigns.com")
})

// Event listeners
window.addEventListener("DOMContentLoaded", () => {
  displayProducts()
})

window.addEventListener("scroll", () => {
  const header = document.querySelector("header")
  if (window.scrollY > 50) {
    header.classList.add("scrolled")
  } else {
    header.classList.remove("scrolled")
  }
})

cartToggle.addEventListener("click", openCart)
closeCartBtn.addEventListener("click", closeCart)
closeModal.addEventListener("click", closeProductModal)
overlay.addEventListener("click", () => {
  closeCart()
  closeProductModal()
})

// Prodigi API integration (simulated)
function createProdigiOrder(orderData) {
  // In a real implementation, you would make an API call to Prodigi
  // to create a print order for the purchased posters
  console.log("Creating Prodigi print order:", orderData)

  // This would typically be done on your server after a successful Stripe payment
  return {
    id: "po-" + Math.random().toString(36).substr(2, 9),
    status: "created",
  }
}

// Page section management
function hideAllSections() {
    document.querySelectorAll('.page-section').forEach(section => {
        section.classList.add('hidden');
    });
    document.querySelectorAll('main > section').forEach(section => {
        section.style.display = 'none';
    });
}

function showMainContent() {
    hideAllSections();
    document.querySelectorAll('main > section').forEach(section => {
        section.style.display = 'block';
    });
    window.scrollTo(0, 0);
}

function showSection(sectionId) {
    hideAllSections();
    const section = document.getElementById(sectionId);
    if (section) {
        section.classList.remove('hidden');
        window.scrollTo(0, 0);
    }
}

// Update checkout button click handler
document.getElementById('checkout-btn').addEventListener('click', async () => {
    const cartItems = JSON.parse(localStorage.getItem('cartItems') || '[]');
    if (cartItems.length === 0) {
        alert('Your cart is empty');
        return;
    }

    try {
        const response = await fetch(`${API_URL}/checkout`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                items: cartItems,
                customerEmail: localStorage.getItem('customerEmail')
            })
        });

        const data = await response.json();
        if (response.ok) {
            // Initialize Stripe Elements
            const stripe = Stripe('pk_live_51PbnbRRut3hoXCRuHV1jx7CxLFOUarhmGYpEqoAAechuMo3O6vSdhGzEj1XLogas2o9kKhRCYruCGCZ7pdkwU7m600cNO9Wq2l');
            
            // Create payment element options
            const options = {
                clientSecret: data.clientSecret,
                appearance: {
                    theme: 'flat',
                    variables: {
                        colorPrimary: '#256F8A',
                        colorBackground: '#EFEEE7',
                        colorText: '#1E1E1E',
                        colorDanger: '#BA3B1A',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                        borderRadius: '4px',
                        spacingUnit: '4px'
                    }
                }
            };

            // Create and mount the payment element
            const elements = stripe.elements(options);
            const paymentElement = elements.create('payment');
            paymentElement.mount('#payment-element');

            // Display order details
            const orderSummary = document.getElementById('order-details');
            orderSummary.innerHTML = ''; // Clear existing content
            
            // Add customer email
            const emailDiv = document.createElement('div');
            emailDiv.classList.add('customer-email');
            emailDiv.innerHTML = `<p>Order confirmation will be sent to: ${localStorage.getItem('customerEmail')}</p>`;
            orderSummary.appendChild(emailDiv);

            // Add items
            let total = 0;
            cartItems.forEach(item => {
                const itemDiv = document.createElement('div');
                itemDiv.innerHTML = `<p>${item.name} x ${item.quantity} - $${(item.price * item.quantity).toFixed(2)}</p>`;
                orderSummary.appendChild(itemDiv);
                total += item.price * item.quantity;
            });

            // Add total
            const totalDiv = document.createElement('div');
            totalDiv.innerHTML = `<strong>Total: $${total.toFixed(2)}</strong>`;
            orderSummary.appendChild(totalDiv);

            // Show checkout section
            showSection('checkout-section');

            // Handle form submission
            const form = document.querySelector("#payment-form");
            form.addEventListener("submit", async (e) => {
                e.preventDefault();
                setLoading(true);

                const { error } = await stripe.confirmPayment({
                    elements,
                    confirmParams: {}
                });

                if (error) {
                    const messageContainer = document.querySelector("#payment-message");
                    messageContainer.textContent = error.message;
                    messageContainer.classList.remove("hidden");
                    setLoading(false);
                } else {
                    // Payment successful
                    localStorage.removeItem('cartItems');
                    updateCartCount();
                    showSection('success-section');
                }
            });

            // Close cart sidebar
            document.getElementById('cart-sidebar').classList.remove('active');
            document.getElementById('overlay').classList.remove('active');
        } else {
            throw new Error(data.error || 'Error creating checkout session');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error creating checkout session: ' + error.message);
    }
});

function setLoading(isLoading) {
    const submitButton = document.querySelector("#submit");
    const spinner = document.querySelector("#spinner");
    const buttonText = document.querySelector("#button-text");

    if (isLoading) {
        submitButton.disabled = true;
        spinner.classList.remove("hidden");
        buttonText.classList.add("hidden");
    } else {
        submitButton.disabled = false;
        spinner.classList.add("hidden");
        buttonText.classList.remove("hidden");
    }
}

// Initialize with main content visible
showMainContent();

async function initiateCheckout() {
    try {
        const email = document.getElementById('customer-email').value;
        if (!email || !email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) {
            throw new Error('Please enter a valid email address');
        }

        localStorage.setItem('customerEmail', email);
        const checkoutButton = document.getElementById('checkout-button');
        const spinner = checkoutButton.querySelector('.spinner');
        const buttonText = checkoutButton.querySelector('.button-text');

        checkoutButton.disabled = true;
        spinner.classList.remove('hidden');
        buttonText.classList.add('hidden');

        const cartData = {
            items: cartItems.map(item => ({
                id: item.id,
                quantity: item.quantity
            })),
            email: email
        };

        const response = await fetch('/api/create-checkout-session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cartData)
        });

        const data = await response.json();
        if (response.ok) {
            // Initialize Stripe Elements
            const stripe = Stripe('pk_live_51PbnbRRut3hoXCRuHV1jx7CxLFOUarhmGYpEqoAAechuMo3O6vSdhGzEj1XLogas2o9kKhRCYruCGCZ7pdkwU7m600cNO9Wq2l');
            
            // Create payment element options with wallet support
            const options = {
                clientSecret: data.clientSecret,
                appearance: {
                    theme: 'flat',
                    variables: {
                        colorPrimary: '#256F8A',
                        colorBackground: '#EFEEE7',
                        colorText: '#1E1E1E',
                        colorDanger: '#BA3B1A',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                        borderRadius: '4px',
                        spacingUnit: '4px'
                    }
                },
                payment: {
                    defaultPaymentMethod: 'card',
                    wallets: {
                        applePay: 'auto',
                        googlePay: 'auto'
                    }
                }
            };

            // Create and mount the payment element
            const elements = stripe.elements(options);
            const paymentElement = elements.create('payment');
            paymentElement.mount('#payment-element');

            // Display order details
            const orderSummary = document.getElementById('order-details');
            orderSummary.innerHTML = ''; // Clear existing content
            
            // Add customer email
            const emailDiv = document.createElement('div');
            emailDiv.classList.add('customer-email');
            emailDiv.innerHTML = `<p>Order confirmation will be sent to: ${email}</p>`;
            orderSummary.appendChild(emailDiv);

            // Add items
            let total = 0;
            cartItems.forEach(item => {
                const itemDiv = document.createElement('div');
                itemDiv.innerHTML = `<p>${item.name} x ${item.quantity} - $${(item.price * item.quantity).toFixed(2)}</p>`;
                orderSummary.appendChild(itemDiv);
                total += item.price * item.quantity;
            });

            // Add total
            const totalDiv = document.createElement('div');
            totalDiv.innerHTML = `<strong>Total: $${total.toFixed(2)}</strong>`;
            orderSummary.appendChild(totalDiv);

            // Show checkout section
            showSection('checkout-section');

            // Handle form submission
            const form = document.querySelector("#payment-form");
            form.addEventListener("submit", async (e) => {
                e.preventDefault();
                setLoading(true);

                const { error } = await stripe.confirmPayment({
                    elements,
                    confirmParams: {
                        return_url: window.location.origin + '/success',
                        payment_method_data: {
                            billing_details: {
                                email: email
                            }
                        }
                    }
                });

                if (error) {
                    const messageContainer = document.querySelector("#payment-message");
                    messageContainer.textContent = error.message;
                    messageContainer.classList.remove("hidden");
                    setLoading(false);
                }
                // No else needed as successful payments will redirect
            });

            // Close cart sidebar
            document.getElementById('cart-sidebar').classList.remove('active');
            document.getElementById('overlay').classList.remove('active');
        } else {
            throw new Error(data.error || 'Error creating checkout session');
        }
    } catch (error) {
        console.error('Error:', error);
        const messageContainer = document.querySelector("#payment-message");
        messageContainer.textContent = error.message;
        messageContainer.classList.remove("hidden");
        setLoading(false);
    }
}

// Email validation function
function validateEmail() {
    const email = document.getElementById('customer-email').value;
    const checkoutButton = document.getElementById('checkout-button');
    const isValid = email && email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/);
    checkoutButton.disabled = !isValid;
    return isValid;
}

