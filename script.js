// Sample product data
const products = [
  {
    id: 1,
    name: "Christ in Gethsemane",
    description: "Powerful depiction of Christ's prayer in Gethsemane",
    price: 0.50,
    image: "assets/poster1.jpg",
  },
  {
    id: 2,
    name: "The First Vision",
    description: "Sacred moment of Joseph Smith's first vision",
    price: 0.50,
    image: "assets/poster2.jpg",
  },
  {
    id: 3,
    name: "The Living Christ",
    description: "Inspiring representation of the resurrected Christ",
    price: 0.50,
    image: "assets/poster3.jpg",
  },
  {
    id: 4,
    name: "The Restoration",
    description: "Symbolic representation of the Restoration",
    price: 0.50,
    image: "assets/poster4.jpg",
  },
  {
    id: 5,
    name: "The Plan of Salvation",
    description: "Beautiful visualization of God's plan",
    price: 0.50,
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
  // Initialize Stripe with your production publishable key and stable API version
  stripe = Stripe('pk_live_51PbnbRRut3hoXCRuHV1jx7CxLFOUarhmGYpEqoAAechuMo3O6vSdhGzEj1XLogas2o9kKhRCYruCGCZ7pdkwU7m600cNO9Wq2l', {
    apiVersion: '2023-10-16', // Using stable API version
    locale: 'en' // Specify locale
  });
  console.log('[DEBUG] Stripe initialized:', stripe); // Added log
  
  // Verify stripe is properly initialized
  if (!stripe || typeof stripe.elements !== 'function') {
    throw new Error('Stripe failed to initialize properly');
  }
} catch (error) {
  console.error("Failed to initialize Stripe:", error)
  console.error('[DEBUG] Stripe initialization FAILED'); // Added log
}

// DOM Elements
const productsGrid = document.getElementById("products-grid")
const filterBtns = document.querySelectorAll(".filter-btn")
const cartToggle = document.getElementById("cart-toggle")
const closeCartBtn = document.getElementById("close-cart")
const productModal = document.getElementById("product-modal")
const closeModal = document.getElementById("close-modal")
const contactLink = document.getElementById("contact-link")

// Initialize cart count visibility
if (cart.length === 0) {
  cartCount.style.display = 'none'
}

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
      </div>
    `

    cartItems.appendChild(cartItem)

    // Add event listeners
    const decreaseBtn = cartItem.querySelector(".decrease")
    const increaseBtn = cartItem.querySelector(".increase")

    decreaseBtn.addEventListener("click", () => {
      decreaseQuantity(item.id)
    })

    increaseBtn.addEventListener("click", () => {
      increaseQuantity(item.id)
    })

    // Update total and count
    total += item.price * item.quantity
    count += item.quantity
  })

  // Update cart total and count
  cartTotal.textContent = `$${total.toFixed(2)}`
  
  // Update cart count and visibility of count badge
  cartCount.textContent = count
  if (count > 0) {
    cartCount.style.display = 'flex'
  } else {
    cartCount.style.display = 'none'
  }

  // Add email input if not already present
  let emailContainer = document.querySelector('.cart-email-container');
  if (!emailContainer && cart.length > 0) {
    emailContainer = document.createElement('div');
    emailContainer.classList.add('cart-email-container');
    emailContainer.innerHTML = `
      <div class="email-input-wrapper">
        <input type="email" id="cart-email" placeholder=" " required>
        <label for="cart-email">Email for Shipping Updates</label>
        <div class="email-validation-message">Please enter a valid email address</div>
      </div>
    `;
    cartItems.insertAdjacentElement('afterend', emailContainer);
    
    // Enable/disable checkout button based on email validity
    const emailInput = emailContainer.querySelector('#cart-email');
    const validationMessage = emailContainer.querySelector('.email-validation-message');
    
    // Initially hide validation message
    validationMessage.style.opacity = '0';
    
    // Add a variable to store the timeout
    let validationTimeout;
    
    emailInput.addEventListener('input', () => {
      // Clear any existing timeout
      if (validationTimeout) {
        clearTimeout(validationTimeout);
      }
      
      const isValid = emailInput.checkValidity();
      
      // Always enable/disable the button immediately
      checkoutBtn.disabled = !isValid;
      
      // If valid, hide message immediately and store email
      if (isValid) {
        validationMessage.style.opacity = '0';
        emailContainer.classList.remove('invalid');
        localStorage.setItem('customerEmail', emailInput.value);
      } else {
        // If invalid, set a timeout to show the message after 1.75 seconds
        validationTimeout = setTimeout(() => {
          if (!emailInput.checkValidity()) {
            validationMessage.style.opacity = '1';
            emailContainer.classList.add('invalid');
          }
        }, 1750); // 1.75 seconds
      }
    });
    
    // Initially disable checkout button
    checkoutBtn.disabled = true;
  } else if (cart.length === 0 && emailContainer) {
    emailContainer.remove();
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

// Handle feedback button click
document.addEventListener('DOMContentLoaded', () => {
  const feedbackBtn = document.getElementById("feedback-btn")
  if (feedbackBtn) {
    feedbackBtn.addEventListener("click", (e) => {
      e.preventDefault()
      const email = "hello@hansenhome.ai"
      const subject = "Website Feedback"
      window.location.href = `mailto:${email}?subject=${encodeURIComponent(subject)}`
    })
  }
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
  showMainContent()
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
    if (cart.length === 0) {
        alert('Your cart is empty');
        return;
    }

    // Save cart items to localStorage for processing
    localStorage.setItem('cartItems', JSON.stringify(cart));
    
    // Close cart sidebar
    closeCart();
    
    // Show checkout section
    showSection('checkout-section');
    
    // Create and show the loading animation
    const loadingAnimation = document.createElement('div');
    loadingAnimation.className = 'checkout-loading-animation';

    // Create a single spinner circle
    const spinner = document.createElement('div');
    spinner.className = 'loading-spinner';

    // Add the spinner to the loading animation container
    loadingAnimation.appendChild(spinner);

    document.body.appendChild(loadingAnimation);

    try {
        // Added log before using stripe
        console.log('[DEBUG] Value of stripe before stripe.elements call:', stripe);
        console.log('[DEBUG] Using publishable key:', 'pk_live_51PbnbRRut3hoXCRuHV1jx7CxLFOUarhmGYpEqoAAechuMo3O6vSdhGzEj1XLogas2o9kKhRCYruCGCZ7pdkwU7m600cNO9Wq2l');

        // Get client ID for this browser/user
        const clientId = getClientId();
        console.log('[DEBUG] Using client ID:', clientId);
        
        // Reset any previous checkout job
        currentCheckoutJob = null;

        const response = await fetch(`${API_URL}/checkout`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                items: cart,
                customerEmail: localStorage.getItem('customerEmail'),
                clientId: clientId
            })
        });

        // Check if the response is successful before proceeding
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error('API Error:', response.status, errorData);
            throw new Error(`Checkout API returned ${response.status}: ${errorData.message || 'Unknown error'}`);
        }

        const data = await response.json();
        
        // Verify we have a valid clientSecret
        if (!data.clientSecret) {
            throw new Error('No client secret returned from API');
        }
        
        const clientSecret = data.clientSecret;
        console.log('Client Secret:', clientSecret);
        
        // Store the job ID and order ID
        currentCheckoutJob = {
            jobId: data.jobId,
            orderId: data.orderId,
            clientId: data.clientId,
            startTime: Date.now()
        };
        
        // Store the current checkout info in sessionStorage
        // This ensures it's limited to this browser tab
        sessionStorage.setItem('currentCheckout', JSON.stringify(currentCheckoutJob));
        console.log('[DEBUG] Checkout job started:', currentCheckoutJob);
        
        // Basic format validation for client secret (should start with 'pi_' for PaymentIntents)
        if (!clientSecret.startsWith('pi_')) {
            console.error('Invalid client secret format:', clientSecret);
            
            // Remove loading animation
            loadingAnimation.classList.add('dispersing');
            setTimeout(() => {
                loadingAnimation.remove();
            }, 1000);
            
            // Display error on the page
            const checkoutSection = document.getElementById('checkout-section');
            if (checkoutSection) {
                const errorElement = document.createElement('div');
                errorElement.className = 'error-message';
                errorElement.style.color = 'red';
                errorElement.style.padding = '20px';
                errorElement.style.marginTop = '20px';
                errorElement.textContent = 'Invalid payment session. Please try again.';
                
                // Insert at the beginning of the checkout section
                checkoutSection.prepend(errorElement);
            }
            
            showSection('checkout-section');
            return; // Don't proceed with Stripe Elements
        }
        
        // Make a copy of the current cart state for order summary
        const currentCartItems = [...cart];
        
        // Remove any existing order summaries
        const existingSummaries = document.querySelectorAll('.order-summary-section');
        existingSummaries.forEach(summary => summary.remove());
        
        // Display order summary in checkout page
        const orderSummarySection = document.createElement('div');
        orderSummarySection.classList.add('order-summary-section');
        
        let summaryHTML = '<h2>Order Summary</h2><div class="order-items">';
        let total = 0;
        
        currentCartItems.forEach(item => {
            summaryHTML += `
                <div class="order-item">
                    <div class="order-item-details">
                        <span class="order-item-name">${item.name}</span>
                        <span class="order-item-quantity">× ${item.quantity}</span>
                    </div>
                    <span class="order-item-price">$${(item.price * item.quantity).toFixed(2)}</span>
                </div>
            `;
            total += item.price * item.quantity;
        });
        
        summaryHTML += `
            <div class="order-total">
                <strong>Total</strong>
                <strong>$${total.toFixed(2)}</strong>
            </div>
            <div class="order-email">
                <span>Order confirmation will be sent to:</span>
                <span class="customer-email">${localStorage.getItem('customerEmail')}</span>
            </div>
        </div>`;
        
        orderSummarySection.innerHTML = summaryHTML;
        
        // Insert order summary before payment element
        const paymentElementContainer = document.querySelector("#payment-element");
        paymentElementContainer.parentElement.insertBefore(orderSummarySection, paymentElementContainer);

        // Create payment element with expanded payment method options
        const appearance = {
            theme: 'stripe',
            variables: {
                colorPrimary: '#0570de',
                colorBackground: '#ffffff',
                colorText: '#30313d',
                colorDanger: '#df1b41',
                fontFamily: 'Ideal Sans, system-ui, sans-serif',
                borderRadius: '4px'
            }
        };

        const paymentElementOptions = {
            layout: {
                type: 'tabs',
                defaultCollapsed: false,
            },
            fields: {
                billingDetails: {
                    email: 'auto'
                }
            },
            paymentMethodOrder: ['card']
        };

        // Initialize Stripe Elements with error handling
        let elements;
        try {
            // Log the client secret format for debugging
            console.log('[DEBUG] Client Secret format check:', {
                length: clientSecret.length,
                startsWithPi: clientSecret.startsWith('pi_'),
                hasUnderscoreSecret: clientSecret.includes('_secret_')
            });
            
            elements = stripe.elements({
                appearance,
                clientSecret
            });

            const paymentElement = elements.create("payment", paymentElementOptions);
            
            // Add detailed logging for element events
            paymentElement.on('ready', function(event) {
                console.log('[DEBUG] Payment element ready:', event);
                
                // Add a transition class to the loading animation
                loadingAnimation.classList.add('dispersing');
                
                // Remove the loading animation after the dispersion animation completes
                setTimeout(() => {
                    loadingAnimation.remove();
                }, 1000); // 1 second for the dispersion animation
            });
            
            paymentElement.on('loaderror', (event) => {
                console.error('Payment element loading error:', event);
                
                // Remove loading animation
                loadingAnimation.classList.add('dispersing');
                setTimeout(() => {
                    loadingAnimation.remove();
                }, 1000);
                
                const messageContainer = document.querySelector("#payment-message");
                messageContainer.textContent = "Failed to load payment form: " + (event.error?.message || "Unknown error");
                messageContainer.classList.remove("hidden");
                setLoading(false);
            });
            
            // Make sure checkout section is visible before mounting
            showSection('checkout-section');
            
            // Add a small timeout to ensure DOM is fully rendered
            setTimeout(() => {
                try {
                    // Check if element exists
                    const paymentElementContainer = document.querySelector("#payment-element");
                    if (!paymentElementContainer) {
                        throw new Error("Payment element container not found in DOM");
                    }
                    
                    // Mount the payment element
                    console.log('[DEBUG] Mounting payment element to', paymentElementContainer);
                    paymentElement.mount("#payment-element");
                    console.log('[DEBUG] Payment element mounted successfully');
                } catch (mountError) {
                    // Remove loading animation
                    loadingAnimation.classList.add('dispersing');
                    setTimeout(() => {
                        loadingAnimation.remove();
                    }, 1000);
                    
                    console.error('Error mounting payment element:', mountError);
                    const messageContainer = document.querySelector("#payment-message");
                    messageContainer.textContent = "Failed to display payment form: " + mountError.message;
                    messageContainer.classList.remove("hidden");
                }
            }, 100);
        } catch (error) {
            // Remove loading animation
            loadingAnimation.classList.add('dispersing');
            setTimeout(() => {
                loadingAnimation.remove();
            }, 1000);
            
            console.error('Error initializing Stripe Elements:', error);
            const messageContainer = document.querySelector("#payment-message");
            messageContainer.textContent = "Failed to initialize payment. Please refresh and try again.";
            messageContainer.classList.remove("hidden");
            return; // Don't proceed further
        }

        // Handle form submission
        const form = document.querySelector("#payment-form");
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            setLoading(true);

            if (!elements) {
                const messageContainer = document.querySelector("#payment-message");
                messageContainer.textContent = "Payment form not loaded properly. Please refresh and try again.";
                messageContainer.classList.remove("hidden");
                setLoading(false);
                return;
            }

            const { error } = await stripe.confirmPayment({
                elements,
                confirmParams: {
                    return_url: window.location.href,
                    payment_method_data: {
                        billing_details: {
                            email: localStorage.getItem('customerEmail')
                        }
                    }
                },
                redirect: "if_required"
            });

            if (error) {
                const messageContainer = document.querySelector("#payment-message");
                messageContainer.textContent = error.message;
                messageContainer.classList.remove("hidden");
                setLoading(false);
                
                // Log the error with job details for troubleshooting
                console.error('Payment confirmation error:', error, 'Job:', currentCheckoutJob);
            } else {
                // Payment successful
                console.log('Payment successful for job:', currentCheckoutJob);
                
                // Clear checkout data but keep client ID
                localStorage.removeItem('cartItems');
                sessionStorage.removeItem('currentCheckout');
                currentCheckoutJob = null;
                
                updateCartCount();
                showSection('success-section');
            }
        });

        // Cart sidebar already closed at the beginning of checkout
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

// Function to test Stripe key match
async function testStripeKeyMatch() {
    try {
        // Test frontend Stripe key
        console.log('[STRIPE TEST] Testing frontend Stripe key...');
        const frontendAccount = await stripe.customers.retrieve('cus_test');
        console.log('[STRIPE TEST] Frontend error is expected, just checking account access');
    } catch (err) {
        // Expected error for non-existent customer, but we'll get the error details
        console.log('[STRIPE TEST] Frontend Stripe account:', err.message);
        // Look for account identifier in the error message
        const accountMatch = err.message.match(/acct_([\w\d]+)/);
        if (accountMatch) {
            console.log('[STRIPE TEST] Frontend account ID hint:', accountMatch[0]);
        }
    }
    
    // Now test the backend
    try {
        console.log('[STRIPE TEST] Testing backend Stripe key...');
        const response = await fetch(`${API_URL}/stripe-test`);
        const data = await response.json();
        console.log('[STRIPE TEST] Backend Stripe account:', data);
        
        if (data.success) {
            alert(`Stripe Test Results:\nFrontend publishable key: pk_test_51Pbnb...\nBackend account: ${data.account_id}`);
        } else {
            alert(`Stripe Test Error:\n${data.error}`);
        }
    } catch (err) {
        console.error('[STRIPE TEST] Backend test error:', err);
        alert(`Stripe test endpoint error: ${err.message}`);
    }
}

// Only for debugging - call this manually in console if needed
// testStripeKeyMatch();

// Add a keyboard shortcut to test Stripe keys (Shift+D)
document.addEventListener('keydown', function(event) {
    // Check if we're on the checkout page
    const checkoutSection = document.getElementById('checkout-section');
    if (event.key === 'D' && event.shiftKey && !checkoutSection.classList.contains('hidden')) {
        console.log('[DEBUG] Running Stripe key test');
        testStripeKeyMatch();
    }
});

// Add function to generate a client ID if it doesn't exist
function getClientId() {
    // Try to get existing client ID from localStorage
    let clientId = localStorage.getItem('clientId');
    
    // If no client ID exists, generate a new one
    if (!clientId) {
        // Generate a UUID-like identifier
        clientId = 'client_' + Math.random().toString(36).substring(2, 15) + 
                   Math.random().toString(36).substring(2, 15);
        // Store it for future use
        localStorage.setItem('clientId', clientId);
    }
    
    return clientId;
}

// Track the current checkout job
let currentCheckoutJob = null;

// Make footer links work from any page
document.addEventListener('DOMContentLoaded', () => {
  // For all navigation links (including footer links)
  const allNavLinks = document.querySelectorAll('nav a, footer a');
  
  allNavLinks.forEach(link => {
    // Skip links with external URLs or email links
    if (link.getAttribute('href') && 
        (link.getAttribute('href').startsWith('http') || 
         link.getAttribute('href').startsWith('mailto:') ||
         link.getAttribute('href') === '#feedback-btn')) {
      return;
    }
    
    link.addEventListener('click', (e) => {
      const href = link.getAttribute('href');
      
      // Skip if no href
      if (!href) return;
      
      // If it's a page anchor
      if (href.startsWith('#')) {
        e.preventDefault();
        const targetId = href.substring(1);
        
        // First return to main content if we're on a special page
        if (document.querySelector('.page-section:not(.hidden)')) {
          showMainContent();
        }
        
        // Then scroll to the section
        setTimeout(() => {
          const targetSection = document.getElementById(targetId);
          if (targetSection) {
            targetSection.scrollIntoView({ behavior: 'smooth' });
          }
        }, 100);
      }
    });
  });
  
  // Add event listener for checkout back link
  const checkoutBackLink = document.getElementById('checkout-back-link');
  if (checkoutBackLink) {
    checkoutBackLink.addEventListener('click', (e) => {
      e.preventDefault();
      
      // Remove loading animation if present
      const loadingAnimation = document.querySelector('.checkout-loading-animation');
      if (loadingAnimation) {
        loadingAnimation.remove();
      }
      
      // Clear checkout state
      const paymentElement = document.getElementById('payment-element');
      if (paymentElement) {
        paymentElement.innerHTML = '';
      }
      
      showMainContent();
    });
  }
});

