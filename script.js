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
const API_URL = "https://YOUR_API_GATEWAY_ID.execute-api.us-west-2.amazonaws.com/prod"

// Initialize Stripe
let stripe
try {
  // Initialize Stripe with your publishable key
  stripe = Stripe('pk_test_YOUR_PUBLISHABLE_KEY');
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

// Checkout
async function checkout() {
  try {
    // Prepare the request body
    const requestBody = {
      items: cart.map(item => ({
        id: item.id,
        quantity: item.quantity
      })),
      customer_email: "customer@example.com" // Replace with actual customer email
    }

    // Make the API call to create a checkout session
    const response = await fetch(`${API_URL}/checkout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    })

    if (!response.ok) {
      throw new Error('Failed to create checkout session')
    }

    const { sessionId } = await response.json()

    // Redirect to Stripe Checkout
    const result = await stripe.redirectToCheckout({
      sessionId: sessionId
    })

    if (result.error) {
      throw new Error(result.error.message)
    }
  } catch (error) {
    console.error('Checkout error:', error)
    alert('Failed to load checkout. Please try again.')
  }
}

// Event Listeners
document.addEventListener("DOMContentLoaded", () => {
  displayProducts()

  // Cart toggle
  cartToggle.addEventListener("click", openCart)
  closeCartBtn.addEventListener("click", closeCart)
  overlay.addEventListener("click", () => {
    closeCart()
    closeProductModal()
  })

  // Close modal
  closeModal.addEventListener("click", closeProductModal)

  // Checkout
  checkoutBtn.addEventListener("click", checkout)

  // Scroll behavior
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault()
      document.querySelector(this.getAttribute('href')).scrollIntoView({
        behavior: 'smooth'
      })
    })
  })
})

