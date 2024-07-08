$(document).ready(function() {
    $('#createUserForm').submit(function(event) {
        var newPassword = $('#new_password').val();
        var confirmPassword = $('#confirm_password').val();

        if (newPassword !== confirmPassword) {
            alert('As senhas não coincidem. Por favor, digite novamente.');
            event.preventDefault(); // Impede o envio do formulário se as senhas não coincidirem
        }
    });
});
