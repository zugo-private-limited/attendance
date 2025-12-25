// --- START OF FILE script.js ---

// Get the main container
const container = document.getElementById("container");

// Get the sign-in and sign-up buttons
const signUpButton = document.getElementById("signUp");
const signInButton = document.getElementById("signIn");

// Add event listeners for switching panels
signUpButton.addEventListener("click", () => {
    container.classList.add("right-panel-active");
});

signInButton.addEventListener("click", () => {
    container.classList.remove("right-panel-active");
});

// Prevent zooming on double tap (iOS)
let lastTouchEnd = 0;
document.addEventListener('touchend', function(event) {
    const now = Date.now();
    if (now - lastTouchEnd <= 300) {
        event.preventDefault();
    }
    lastTouchEnd = now;
}, false);

// Improve mobile form input handling
document.addEventListener('DOMContentLoaded', function() {
    const inputs = document.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        // Prevent auto-zoom on input focus
        input.addEventListener('focus', function() {
            if (window.innerWidth <= 768) {
                // Scroll to input
                setTimeout(() => {
                    input.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 300);
            }
        });
    });
});