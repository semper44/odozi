$(document).ready(function() {
    $('.github-install').click(function(e) {
        e.preventDefault();
        // const apiUrl = window.ENV.API_URL;
        // console.log(apiUrlL, "sreher")

        // $.ajax({
        //     url: 'https://github.com/apps/odozy-ci-agent/installations/new',
        //     method: "POST",
        //     contentType: "application/json",
        //     data: JSON.stringify({ task: "task, deadline: taskDeadline "}),

        //     success: function (response) {
        //         // 3. Trigger the typing effect
        //         console.log(response.data, response, "response from ai chat")               
        //     },

        //     error: function (err) {
        //         let message = "Something went wrong";
        //         const target = $("#analyze-with-ai-response-content");
        //         switch (err.status) {
        //             case 400:
        //                 message = "Bad request";
        //                 break;
        //             case 401:
        //                 message = "Unauthorized";
        //                 break;
        //             case 403:
        //                 message = "Forbidden";
        //                 break;
        //             case 404:
        //                 message = "Not found";
        //                 break;
        //             case 429:
        //                 message = "⚠️ AI limit reached. Please try again next day.";
        //                 break;
        //             case 500:
        //                 message = "AI client error. Try again.";
        //                 break;
        //             default:
        //                 message = err.responseJSON?.error || message;
        //         }
        //     }
        // });

         console.log("button clicked");

        window.location.href =
            "https://github.com/apps/odozy-ci-agent/installations/new";

    });

    })
