function showLoader() {
	const loader = document.querySelector('#page-loader');
	loader.classList.remove('hidden','animate-fade-out');
	loader.classList.add('animate-fade-in');

}
function hideLoader() {
	const loader = document.querySelector('#page-loader');
	loader.classList.remove('animate-fade-in');
	loader.classList.add('animate-fade-out');
	
	// Hide completely after animation ends
	loader.addEventListener('animationend', () => {
		if (loader.classList.contains('animate-fade-out')) {
			loader.classList.add('hidden');
		}
	});
}
document.addEventListener('DOMContentLoaded', function () {
	// Initialize Swiper only if it exists (for homepage carousels)
    if (typeof Swiper !== 'undefined') {
        // Company carousel (REMOVED - Replaced with custom CSS carousel)
        // const companyCarousel = document.querySelector('.company-carousel');
        // if (companyCarousel) { ... }

        // Testimonials carousel
        const testimonialsCarousel = document.querySelector('.testimonials-carousel');
        if (testimonialsCarousel) {
            new Swiper('.testimonials-carousel', {
                loop: true,
                slidesPerView: 1,
                spaceBetween: 30,
                navigation: {
                    nextEl: '.swiper-button-next',
                    prevEl: '.swiper-button-prev',
                },
                pagination: {
                    el: '.swiper-pagination',
                    clickable: true,
                },
                breakpoints: {
                    1024: {
                        slidesPerView: 3,
                        spaceBetween: 50,
                    },
                },
            });
        }
    }



    // Parallax effect for Hero Image on index.html
    const heroParallaxImg = document.getElementById('hero-parallax-img');
    const jobParallaxImg = document.getElementById('job-parallax-img'); // Get the new image

    if (heroParallaxImg || jobParallaxImg) { // Only run if at least one parallax image exists
        window.addEventListener('scroll', () => {
            const scrollPosition = window.scrollY;
            if (heroParallaxImg) {
                heroParallaxImg.style.transform = `translateY(${scrollPosition * 0.2}px)`;
            }
            if (jobParallaxImg) {
                jobParallaxImg.style.transform = `translateY(${-scrollPosition * 0.1}px)`; // Opposite direction, slower speed
            }
        });
    }

    // Form Micro-interactions (Login/Register pages)
    const formInputs = document.querySelectorAll('.w-full.p-3.border');
    formInputs.forEach(input => {
        const label = input.previousElementSibling; // Assumes label is sibling before input
        if (label && label.classList.contains('input-label')) {
            // Initial check for pre-filled fields
            if (input.value !== '') {
                label.classList.add('active');
            }

            input.addEventListener('focus', () => {
                label.classList.add('active');
            });

            input.addEventListener('blur', () => {
                if (input.value === '') {
                    label.classList.remove('active');
                }
            });
        }
    });

    // Show/Hide Password Toggle
    const togglePassword = document.getElementById('togglePassword');
    if (togglePassword) {
        togglePassword.addEventListener('click', function () {
            const passwordInput = this.previousElementSibling; // Assumes input is sibling before toggle
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);

            // Toggle eye icon (you'd need two SVG paths or change the SVG itself)
            // For simplicity, we'll just change color or add a class if you have different icons
            this.querySelector('svg').classList.toggle('text-primary'); // Example: change color
        });
    }

    // Button Loading Spinner and Disabled State
    const loginForm = document.querySelector('form'); // Assuming one form per page
    const submitButton = document.getElementById('login-button') || document.getElementById('register-button');
    const spinner = document.getElementById('login-spinner') || document.getElementById('register-spinner');

    if (loginForm && submitButton && spinner) {
        loginForm.addEventListener('submit', function (event) {
            event.preventDefault(); // Prevent actual form submission

            submitButton.disabled = true;
            spinner.classList.remove('hidden');
            submitButton.querySelector('span:not(.spinner)').classList.add('opacity-0'); // Hide text

            // Simulate API call
            setTimeout(() => {
                submitButton.disabled = false;
                spinner.classList.add('hidden');
                submitButton.querySelector('span:not(.spinner)').classList.remove('opacity-0'); // Show text
                alert('Formulario enviado (simulado)!');
            }, 2000);
        });
    }

    // --- CV Upload Modal Logic ---
    const cvModal = document.getElementById('cv-upload-modal');
    if (cvModal) {
        // Modal components
        const openModalBtn = document.getElementById('open-cv-modal-btn');
        const closeModalBtn = document.getElementById('close-cv-modal-btn');
        const cancelBtn = document.getElementById('cancel-upload-btn');
        const modalPanel = document.getElementById('cv-modal-panel');
        const profileNameInput = document.getElementById('cv-profile-name');
        
        // File related components
        const fileInput = document.getElementById('cv-file-input');
        const fileDropArea = document.getElementById('file-drop-area');
        const fileNameDisplay = document.getElementById('file-name-display');
        const filePreviewContainer = document.getElementById('file-preview-container');
        const pdfPreviewIframe = document.getElementById('pdf-preview-iframe');
        const changeFileBtn = document.getElementById('change-file-btn');

        // Save Button components
        const saveBtn = document.getElementById('save-cv-btn');
        const saveBtnContent = document.getElementById('save-btn-content');
        const successBtnContent = document.getElementById('success-btn-content');
        const saveSpinner = document.getElementById('save-cv-spinner');

        // Progress Bar
        const progressBarContainer = document.getElementById('progress-bar-container');
        const progressBar = document.getElementById('progress-bar');

        let selectedFile = null;
        let objectUrl = null; 

        const openModal = () => {
            cvModal.classList.remove('hidden');
            if (modalPanel) {
                document.body.style.overflow = 'hidden';
                setTimeout(() => modalPanel.classList.remove('opacity-0', 'scale-95'), 10);
            }
        };

        const closeModal = () => {
            if (modalPanel) {
                modalPanel.classList.add('opacity-0', 'scale-95');
                setTimeout(() => {
                    cvModal.classList.add('hidden');
                    document.body.style.overflow = '';
                    resetModalState();
                }, 300);
            }
        };

        const resetModalState = () => {
            selectedFile = null;
            if (fileInput) fileInput.value = '';
            if (fileNameDisplay) fileNameDisplay.textContent = '';
            if (profileNameInput) profileNameInput.value = '';

            if (saveBtn) {
                saveBtn.disabled = true;
                saveBtn.classList.remove('bg-green-500');
                saveBtn.classList.add('bg-primary');
            }
            if (successBtnContent) successBtnContent.classList.add('hidden');
            if (saveBtnContent) saveBtnContent.classList.remove('hidden');
            if (saveSpinner) saveSpinner.classList.add('hidden');
            if (saveBtnContent && saveBtnContent.querySelector('span:last-child')) {
                saveBtnContent.querySelector('span:last-child').classList.remove('hidden');
            }

            if (progressBar) progressBar.style.width = '0%';
            if (progressBarContainer) progressBarContainer.classList.add('hidden');

            if (fileDropArea) fileDropArea.classList.remove('hidden', 'border-primary');
            if (filePreviewContainer) filePreviewContainer.classList.add('hidden');
            if (fileNameDisplay) fileNameDisplay.classList.add('hidden');

            if (objectUrl) {
                URL.revokeObjectURL(objectUrl);
                objectUrl = null;
            }
            if (pdfPreviewIframe) pdfPreviewIframe.src = '';
        };

        const handleFileSelect = (file) => {
            if (!file) return;

            selectedFile = file;
            if (saveBtn) saveBtn.disabled = false;
            if (fileNameDisplay) fileNameDisplay.textContent = `Archivo: ${file.name}`;

            if (file.type === 'application/pdf') {
                if (objectUrl) URL.revokeObjectURL(objectUrl);
                objectUrl = URL.createObjectURL(file);
                if (pdfPreviewIframe) pdfPreviewIframe.src = objectUrl;
                if (filePreviewContainer) filePreviewContainer.classList.remove('hidden');
                if (fileDropArea) fileDropArea.classList.add('hidden');
                if (fileNameDisplay) fileNameDisplay.classList.add('hidden');
            } else {
                if (filePreviewContainer) filePreviewContainer.classList.add('hidden');
                if (fileDropArea) fileDropArea.classList.add('hidden');
                if (fileNameDisplay) fileNameDisplay.classList.remove('hidden');
            }
        };

        // --- Event Listeners ---
        if (openModalBtn) openModalBtn.addEventListener('click', openModal);
        if (closeModalBtn) closeModalBtn.addEventListener('click', closeModal);
        if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
        
        cvModal.addEventListener('click', (e) => {
            if (e.target === cvModal) closeModal();
        });
        
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !cvModal.classList.contains('hidden')) closeModal();
        });

        if (fileInput) fileInput.addEventListener('change', () => handleFileSelect(fileInput.files[0]));
        if (changeFileBtn) changeFileBtn.addEventListener('click', () => fileInput.click());

        if (fileDropArea) {
            fileDropArea.addEventListener('dragover', (e) => { e.preventDefault(); fileDropArea.classList.add('border-primary'); });
            fileDropArea.addEventListener('dragleave', () => fileDropArea.classList.remove('border-primary'));
            fileDropArea.addEventListener('drop', (e) => {
                e.preventDefault();
                fileDropArea.classList.remove('border-primary');
                handleFileSelect(e.dataTransfer.files[0]);
            });
        }

        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                if (!selectedFile || (profileNameInput && profileNameInput.value.trim() === '')) {
                    alert('Por favor, completa todos los campos y selecciona un archivo.');
                    return;
                }

                // --- Loading State ---
                saveBtn.disabled = true;
                if (saveSpinner) saveSpinner.classList.remove('hidden');
                if (saveBtnContent && saveBtnContent.querySelector('span:last-child')) {
                    saveBtnContent.querySelector('span:last-child').classList.add('hidden');
                }
                if (progressBarContainer) progressBarContainer.classList.remove('hidden');
                if (progressBar) progressBar.style.width = '0%';

                // --- Simulate Upload ---
                let progress = 0;
                const interval = setInterval(() => {
                    progress += 10;
                    if (progressBar) progressBar.style.width = `${progress}%`;
                    if (progress >= 100) {
                        clearInterval(interval);

                        // --- Success State ---
                        if (saveBtnContent) saveBtnContent.classList.add('hidden');
                        if (successBtnContent) successBtnContent.classList.remove('hidden');
                        saveBtn.classList.remove('bg-primary');
                        saveBtn.classList.add('bg-green-500');

                        // --- Auto Close ---
                        setTimeout(() => {
                            closeModal();
                        }, 1500); 
                    }
                }, 150);
            });
        }
    }


});
