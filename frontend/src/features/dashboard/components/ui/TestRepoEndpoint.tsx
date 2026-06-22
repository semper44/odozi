import { useState } from 'react';
import { toast } from 'react-toastify';

export default function TestRepoEndpoint() {
  const [isPending, setIsPending] = useState(false);
  const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL || 'http://127.0.0.1:8000';

  // 1. Hardcoded test payload mirroring your required backend data keys
  const testPayload = {
    workspace: "olive corp",
    repositories: [
      {
        repo_id: 102938471,
        repo_name: "odozi",
        repo_owner: "semper44",
        repo_full_name: "semper44/odozi"
      },
      {
        repo_id: 204958112,
        repo_name: "django-backend",
        repo_owner: "semper44",
        repo_full_name: "semper44/django-backend"
      },
      {
        repo_id: 401928374,
        repo_name: "bandit-parser",
        repo_owner: "cyber-defense-core",
        repo_full_name: "cyber-defense-core/bandit-parser"
      }
    ],
    // The explicit selection subset you want to create or match against
    selected: ["102938471", "401928374"] 
  };

  const handleTestTrigger = async () => {
    setIsPending(true);
    
    // Create a temporary diagnostic alert so you know the script started running
    const toastId = toast.info("Firing bulk creation request...", { autoClose: false });

    try {
      // 2. Pointing directly to your clean endpoint location path URL
      const response = await fetch(`${backendUrl}/dashboard/api/repos/create/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(testPayload),
      });

      const data = await response.json();

      // Clear the temporary processing alert
      toast.dismiss(toastId);

      if (!response.ok) {
        throw new Error(data.error || `Server responded with status ${response.status}`);
      }

      // 3. Beautiful success toast utilizing your linear color gradient styling 🌈
      toast.success(data.message || "Bulk operation completed!", {
        position: "top-right",
        autoClose: 3000,
        theme: "dark",
        style: {
          background: "linear-gradient(to right, #00b09b, #96c93d)",
          color: "#fff"
        }
      });
      
      console.log("Backend Response:", data);

    } catch (err: any) {
      toast.dismiss(toastId);
      // Fallback error alert if structural crashes occur
      toast.error(`❌ View Failure: ${err.message}`, {
        position: "top-right",
        autoClose: 4000,
        theme: "colored"
      });
      console.error("Test Request Failed:", err);
    } finally {
      setIsPending(false);
    }
  };

  return (
    <div className="p-6 bg-slate-50 border border-slate-200 rounded-2xl max-w-md my-4 shadow-sm">
      {/* Root ToastContainer in App handles toasts; avoid duplicate containers here */}

      <button
        onClick={handleTestTrigger}
        disabled={isPending}
        className={`w-full py-2.5 px-4 rounded-xl font-semibold text-sm shadow transition-all duration-150 cursor-pointer ${
          isPending 
            ? 'bg-slate-400 text-slate-200 cursor-not-allowed' 
            : 'bg-indigo-600 hover:bg-indigo-700 text-white active:scale-[0.98]'
        }`}
      >
        {isPending ? 'Processing Bulk Query...' : 'Run Endpoint Test'}
      </button>
    </div>
  );
}
