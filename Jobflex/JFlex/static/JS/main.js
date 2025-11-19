function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Function to open and populate the apply modal
function openApplyModal(offerId) {
    const modalPlaceholder = document.getElementById('apply-modal-placeholder');
    if (!modalPlaceholder) {
        console.error("Placeholder 'apply-modal-placeholder' not found!");
        return;
    }

    // Show a temporary loading state
    modalPlaceholder.innerHTML = `
        <div id="apply-modal-loading" class="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm flex items-center justify-center z-50">
            <div class="w-12 h-12 border-4 border-white border-t-transparent rounded-full animate-spin"></div>
        </div>
    `;
    
    fetch(`/apply/${offerId}/`, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => { 
                throw new Error(`Server error: ${response.status}. Body: ${text.substring(0, 500)}`);
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.html) {
            modalPlaceholder.innerHTML = data.html;
            
            const modal = document.getElementById('apply-modal');
            const modalPanel = document.getElementById('apply-modal-panel');
            if (modal && modalPanel) {
                modal.classList.remove('hidden');
                document.body.classList.add('overflow-hidden');
                setTimeout(() => modalPanel.classList.remove('scale-95', 'opacity-0'), 50);
            } else {
                console.error("Injected HTML but could not find #apply-modal or #apply-modal-panel.");
            }

        } else if (data.error) {
            // Clear the loading spinner and close modal
            const modalPlaceholder = document.getElementById('apply-modal-placeholder');
            if (modalPlaceholder) modalPlaceholder.innerHTML = '';
            document.body.classList.remove('overflow-hidden');

            alert(data.message); // Show the error message from the server
            
            // If the error is 'already_applied', disable the button on the main page
            if (data.error === 'already_applied') {
                // 'offerId' is available from the outer scope of openApplyModal
                const applyButtonOnPage = document.querySelector(`#open-apply-modal-btn[data-offer-id="${offerId}"]`);
                if (applyButtonOnPage) {
                    applyButtonOnPage.disabled = true;
                    applyButtonOnPage.textContent = 'Postulado';
                }
            } 
            // If the error requires a redirect (e.g., no CV), perform the redirect
            else if (data.redirect_url) {
                window.location.href = data.redirect_url;
            }
        }
    })
    .catch(error => {
        console.error('Error opening modal:', error);
        alert('Ocurrió un error al intentar abrir el modal de postulación. Por favor, intente de nuevo.');
        closeApplyModal();
    });
}

// Function to close the apply modal
function closeApplyModal() {
    const modalPlaceholder = document.getElementById('apply-modal-placeholder');
    const modal = document.getElementById('apply-modal');
    
    if (modal) {
        const modalPanel = document.getElementById('apply-modal-panel');
        document.body.classList.remove('overflow-hidden');
        
        if (modalPanel) {
            modalPanel.classList.add('scale-95', 'opacity-0');
        }
        
        setTimeout(() => {
            if (modalPlaceholder) {
                modalPlaceholder.innerHTML = '';
            } else {
                modal.remove();
            }
        }, 300);
    }
}

async function handleApplicationSubmit(form, offerId) {
    const submitBtn = form.querySelector('#submit-application-btn');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Enviando...';
    
    const formData = new FormData(form);
    try {
        const response = await fetch(`/apply/${offerId}/`, {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        if (!response.ok) throw data;

        alert(data.message || '¡Postulación enviada!');
        closeApplyModal();
        const applyButtonOnPage = document.querySelector(`#open-apply-modal-btn[data-offer-id="${offerId}"]`);
        if (applyButtonOnPage) {
            applyButtonOnPage.disabled = true;
            applyButtonOnPage.textContent = 'Postulado';
        }
    } catch (error) {
        alert(error.message || 'Ocurrió un error al postular.');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Enviar Postulación';
    }
}

async function handleInlineProfileSave(formFieldsContainer) {
    const saveBtn = formFieldsContainer.querySelector('#save-inline-edit');
    if (!saveBtn) return;

    saveBtn.disabled = true;
    saveBtn.textContent = 'Guardando...';

    const formData = new FormData();
    // Manually find and append all input, select, and textarea fields within the container
    formFieldsContainer.querySelectorAll('input, select, textarea').forEach(field => {
        if (field.name) {
            formData.append(field.name, field.value);
        }
    });
    
    // The CSRF token is not in the form fields, so we need to get it from the main apply-form
    const mainApplyForm = document.getElementById('apply-form');
    if (mainApplyForm) {
        const csrfToken = mainApplyForm.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfToken) {
            formData.append('csrfmiddlewaretoken', csrfToken.value);
        }
    }

    try {
        const response = await fetch('/update-profile-modal/', {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest' } // CSRF is in the body, no need for X-CSRFToken header
        });
        const data = await response.json();
        if (!response.ok) throw data;

        // Update the UI with the new data
        const rutSpan = document.getElementById('modal-profile-rut');
        const telSpan = document.getElementById('modal-profile-telefono');
        const citySpan = document.getElementById('modal-profile-ciudad');
        if(rutSpan) rutSpan.textContent = data.updated_data.rut;
        if(telSpan) telSpan.textContent = data.updated_data.telefono;
        if(citySpan) citySpan.textContent = data.updated_data.ubicacion;

        // Hide the edit form and show the display view
        const editFormDiv = document.getElementById('user-data-edit-form');
        const displayDiv = document.getElementById('user-data-display');
        if(editFormDiv) {
            editFormDiv.classList.add('hidden');
            editFormDiv.innerHTML = '';
        }
        if(displayDiv) displayDiv.classList.remove('hidden');

    } catch (error) {
        alert(error.message || 'Error al guardar el perfil.');
        saveBtn.disabled = false;
        saveBtn.textContent = 'Guardar';
    }
}

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
                saveBtnContent.querySelector('span:last-child').classList.add('hidden');
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


    }

    // --- Application Modal Logic ---
    const mainContainer = document.getElementById('job-search-main');
    if (mainContainer) {
        mainContainer.addEventListener('click', function(event) {
            const applyBtn = event.target.closest('#open-apply-modal-btn');
            const anonApplyBtn = event.target.closest('.apply-btn-anon');

            if (applyBtn) {
                event.preventDefault();
                const offerId = applyBtn.dataset.offerId;
                openApplyModal(offerId);
            } else if (anonApplyBtn) {
                event.preventDefault();
                const authModal = document.getElementById('auth-modal');
                if (authModal) {
                    authModal.classList.remove('hidden');
                }
            }
        });
    }

    const modalPlaceholder = document.getElementById('apply-modal-placeholder');
    if (modalPlaceholder) {
        // Main delegation for modal actions
        modalPlaceholder.addEventListener('click', function(event) {
            // Close modal on background click or cancel button
            if (event.target.id === 'apply-modal' || event.target.closest('#cancel-apply-btn')) {
                closeApplyModal();
            }

            // Handle User Data Toggle
            const toggleBtn = event.target.closest('#user-data-toggle-btn');
            if (toggleBtn) {
                const collapsibleSection = document.getElementById('user-data-collapsible-section');
                const chevron = toggleBtn.querySelector('svg');
                const cvListContainer = document.getElementById('cv-list-container');

                if (collapsibleSection && chevron && cvListContainer) {
                    const isCurrentlyVisible = !collapsibleSection.classList.contains('hidden');
                    
                    collapsibleSection.classList.toggle('hidden');
                    chevron.classList.toggle('rotate-180');

                    if (isCurrentlyVisible) {
                        // It was visible, now it's collapsing. Expand the CV list.
                        cvListContainer.classList.remove('max-h-48');
                        cvListContainer.classList.add('max-h-80'); // 20rem
                    } else {
                        // It was hidden, now it's expanding. Shrink the CV list.
                        cvListContainer.classList.remove('max-h-80');
                        cvListContainer.classList.add('max-h-48'); // 12rem
                    }
                }
            }

            // Inline Profile Edit Actions
            const userDataContainer = event.target.closest('#user-data-container');
            if (userDataContainer) {
                const editBtn = event.target.closest('#edit-profile-in-modal-btn');
                const cancelEditBtn = event.target.closest('#cancel-inline-edit');
                const displayDiv = document.getElementById('user-data-display');
                const formDiv = document.getElementById('user-data-edit-form');

                if (editBtn) {
                    fetch('/get-profile-edit-form/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                    .then(response => response.json())
                    .then(data => {
                        if (data.html) {
                            alert('DEBUG: Injecting the following HTML into edit form container:\n\n' + data.html);
                            formDiv.innerHTML = data.html;
                            displayDiv.classList.add('hidden');
                            formDiv.classList.remove('hidden');
                        }
                    });
                }

                if (cancelEditBtn) {
                    formDiv.classList.add('hidden');
                    displayDiv.classList.remove('hidden');
                    formDiv.innerHTML = '';
                }
            }

            // Handle Inline Profile Save Button Click
            const saveProfileBtn = event.target.closest('#save-inline-edit');
            if (saveProfileBtn) {
                event.preventDefault();
                event.stopPropagation();
                const formFieldsContainer = saveProfileBtn.closest('#inline-profile-form-fields');
                if (formFieldsContainer) {
                    handleInlineProfileSave(formFieldsContainer);
                }
            }

            // CV Upload Actions
            const uploadCvBtn = event.target.closest('#upload-cv-btn-modal');
            const cancelUploadCvBtn = event.target.closest('#cancel-upload-cv-modal');
            const cvSelectionSection = document.getElementById('cv-selection-section');
            const uploadCvSection = document.getElementById('upload-cv-section');
            const modalFooter = document.getElementById('apply-modal-footer');

            if (uploadCvBtn) {
                if (cvSelectionSection) cvSelectionSection.classList.add('hidden');
                if (uploadCvSection) uploadCvSection.classList.remove('hidden');
                if (modalFooter) modalFooter.classList.add('hidden');
            }

            if (cancelUploadCvBtn) {
                if (uploadCvSection) uploadCvSection.classList.add('hidden');
                if (cvSelectionSection) cvSelectionSection.classList.remove('hidden');
                if (modalFooter) modalFooter.classList.remove('hidden');

                // Clear form fields
                const uploadForm = document.getElementById('upload-cv-form-modal');
                if (uploadForm) uploadForm.reset();
                const cvFileNameDisplay = document.getElementById('cv-file-name-display');
                if (cvFileNameDisplay) cvFileNameDisplay.textContent = '';
            }
        });

        // Delegation for form submissions
        modalPlaceholder.addEventListener('submit', async function(event) {
            event.preventDefault();
            const formId = event.target.id;

            if (formId === 'apply-form') {
                const form = event.target;
                const offerId = form.querySelector('[name=offer_id]').value;
                handleApplicationSubmit(form, offerId);

            } else if (formId === 'upload-cv-form-modal') {
                const form = event.target;
                const submitBtn = form.querySelector('#submit-upload-cv-modal');
                const originalBtnText = submitBtn.textContent;
                submitBtn.disabled = true;
                submitBtn.textContent = 'Subiendo...';

                const formData = new FormData(form);
                try {
                    const response = await fetch('/upload-cv-modal/', {
                        method: 'POST',
                        body: formData,
                        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken') }
                    });
                    const data = await response.json();

                    if (!response.ok) {
                        // Handle validation errors or other server-side errors
                        let errorMessage = data.message || 'Error al subir el CV.';
                        if (data.errors) {
                            errorMessage += '\n' + Object.values(data.errors).map(e => e[0].message).join('\n');
                        }
                        alert(errorMessage);
                        throw new Error(errorMessage);
                    }

                    alert(data.message || '¡CV subido con éxito!');
                    
                    // Dynamically add the new CV to the selection list
                    const cvSelectionSection = document.getElementById('cv-selection-section');
                    const cvListDiv = cvSelectionSection.querySelector('div.space-y-3');
                    if (cvListDiv) {
                        const newCvHtml = `
                            <label for="cv_${data.cv.id_cv_user}" class="flex items-center p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
                                <input type="radio" id="cv_${data.cv.id_cv_user}" name="selected_cv" value="${data.cv.id_cv_user}" class="h-4 w-4 text-primary border-gray-300 focus:ring-primary" checked>
                                <div class="ml-3">
                                    <p class="font-bold text-dark">${data.cv.nombre_cv}</p>
                                    <p class="text-sm text-secondary">${data.cv.cargo_asociado} - ${data.cv.tipo_cv === 'creado' ? 'Creado en JobFlex' : 'Subido'}</p>
                                </div>
                            </label>
                        `;
                        // If there was a "No tienes ningún CV" message, remove it
                        const noCvMessage = cvListDiv.querySelector('p.text-center');
                        if (noCvMessage) noCvMessage.remove();
                        cvListDiv.insertAdjacentHTML('afterbegin', newCvHtml); // Add new CV at the top
                    }

                    // Re-enable the "Enviar Postulación" button if it was disabled
                    const submitApplicationBtn = document.getElementById('submit-application-btn');
                    if (submitApplicationBtn) submitApplicationBtn.disabled = false;

                    // Hide upload section and show selection section
                    const uploadSection = document.getElementById('upload-cv-section');
                    const selectionSection = document.getElementById('cv-selection-section');
                    const modalFooter = document.getElementById('apply-modal-footer');

                    if (uploadSection) uploadSection.classList.add('hidden');
                    if (selectionSection) selectionSection.classList.remove('hidden');
                    if (modalFooter) modalFooter.classList.remove('hidden');
                    
                    form.reset(); // Clear the upload form
                    const fileNameDisplay = document.getElementById('cv-file-name-display');
                    if (fileNameDisplay) fileNameDisplay.textContent = ''; // Clear file name display

                } catch (error) {
                    console.error('Error uploading CV:', error);
                    alert(error.message || 'Ocurrió un error al subir el CV.');
                } finally {
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalBtnText;
                }
            }
        });

        // Event listener for file input change to display file name
        modalPlaceholder.addEventListener('change', function(event) {
            if (event.target.id === 'cv-file-input-modal') {
                const fileNameDisplay = document.getElementById('cv-file-name-display');
                if (event.target.files.length > 0) {
                    fileNameDisplay.textContent = `Archivo seleccionado: ${event.target.files[0].name}`;
                } else {
                    fileNameDisplay.textContent = '';
                }
            }
        });
    }
});