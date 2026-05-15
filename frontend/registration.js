$(document).ready(function() {
    // 1. Parse the URL parameters to extract the authorization code
    const urlParams = new URLSearchParams(window.location.search);
    const githubCode = urlParams.get('code');

    if (githubCode) {
        $('#status-message').text('Authenticating with backend server...');

        // 2. Send the code to your dj-rest-auth GitHub endpoint
        $.ajax({
            url: 'http://127.0.0', // Your exact Django API endpoint
            type: 'POST',
            contentType: 'application/json',
            dataType: 'json',
            // Ensure cookies (JWTs) are sent and stored correctly across origins
            xhrFields: {
                withCredentials: true 
            },
            data: JSON.stringify({
                code: githubCode
            }),
            success: function(response) {
                // Account created/verified successfully! Django has injected HttpOnly JWT cookies.
                $('#status-message').text('Login successful! Redirecting...');
                
                // Redirect user to their private dashboard
                setTimeout(function() {
                    window.location.href = '/dashboard.html';
                }, 1500);
            },
            error: function(xhr, status, error) {
                console.error('Authentication Error:', xhr.responseText);
                $('#status-message').text('Authentication failed. Please try again.');
            }
        });
    } else {
        $('#status-message').text('No authorization code found. Please log in.');
    }
});
