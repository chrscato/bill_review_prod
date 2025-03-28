// Theme management
const themeSwitch = document.getElementById('darkModeSwitch');
const themePreference = localStorage.getItem('theme') || 'light';

// Set initial theme
document.documentElement.setAttribute('data-theme', themePreference);
themeSwitch.checked = themePreference === 'dark';

// Update icon based on theme
updateThemeIcon(themePreference);

// Add event listener for theme switch
themeSwitch.addEventListener('change', function() {
    const newTheme = this.checked ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
});

// Function to update theme icon
function updateThemeIcon(theme) {
    const iconElement = document.querySelector('.form-check-label i');
    if (iconElement) {
        if (theme === 'dark') {
            iconElement.classList.remove('bi-sun-fill');
            iconElement.classList.add('bi-moon-fill');
        } else {
            iconElement.classList.remove('bi-moon-fill');
            iconElement.classList.add('bi-sun-fill');
        }
    }
}

// Check system preference on page load
function checkSystemPreference() {
    if (localStorage.getItem('theme')) return; // User has set preference
    
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.setAttribute('data-theme', 'dark');
        themeSwitch.checked = true;
        updateThemeIcon('dark');
    }
}

// Check system preference
checkSystemPreference();

// Listen for system preference changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    if (!localStorage.getItem('theme')) { // Only if user hasn't set preference
        const newTheme = e.matches ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', newTheme);
        themeSwitch.checked = e.matches;
        updateThemeIcon(newTheme);
    }
}); 