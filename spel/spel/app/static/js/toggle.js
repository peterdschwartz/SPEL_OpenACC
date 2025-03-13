
function attachToggleListeners() {
    let toggler = document.getElementsByClassName("box");
    for (let i = 0; i < toggler.length; i++) {
        toggler[i].addEventListener("click", function() {
            this.parentElement.querySelector(".child").classList.toggle("active");
            this.classList.toggle("check-box");
        });
    }

}

document.addEventListener("DOMContentLoaded", (event) => {
    console.log("Attaching Toggle All Button")
    const toggleAllButton = document.getElementById('toggle-all-button');
    if (toggleAllButton) {
        toggleAllButton.addEventListener('click', () => {
            const children = document.querySelectorAll('.child');
            const boxes = document.querySelectorAll('.box');
            // make arrays
            const any_active = Array.from(children).some(child => child.classList.contains('active'));
            children.forEach(child => child.classList.toggle("active", !any_active))
            boxes.forEach(box => box.classList.toggle("check-box", !any_active))
        });
    } else {
        console.error("Toggle All Button not found in the DOM!");
    }
})

// Attach listeners after HTMX updates (if HTMX is used)
document.body.addEventListener('htmx:afterSwap', () => {
    console.log("HTMX content swapped.");

    console.log("event:");
    if (event.detail.target.id === "modalContent") {
        console.log("Showing Modal")
        document.getElementById("modalOverlay").style.display = 'flex';
    }
    attachToggleListeners();
});

// Hide the modal if the overlay is clicked.
document.getElementById("modalOverlay").addEventListener("click", function() {
    this.style.display = "none";
});

