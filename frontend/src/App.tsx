import { useState } from 'react'
import { RouterProvider } from "react-router-dom";
import { router } from "./app/router";
import { QueryProvider } from "./app/providers/QueryProvider";
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

export default function App() {
  // temporary debug toast to verify global container rendering
  // Remove after verification
  useState(() => {
    try {
      console.log('Debug: attempting to show toast on App mount');
      const id = toast.info('Debug: toast container test', { autoClose: 2000 });
      console.log('Debug: toast id', id);
      if (typeof window !== 'undefined' && document) {
        // Give React a tick to render the container, then probe the DOM
        setTimeout(() => {
          const container = document.querySelector('.Toastify__toast-container');
          console.log('Debug: Toast container present?', !!container, container);
        }, 100);
      }
    } catch (err) {
      console.error('Debug: toast failed', err);
    }
  });
  return (
    <QueryProvider>
       <ToastContainer
         aria-label="System Notifications"
         position="top-right"
         autoClose={4000}
         hideProgressBar={false}
         newestOnTop={true}
         closeOnClick
         rtl={false}
         pauseOnFocusLoss
         draggable
         pauseOnHover
         theme="colored"
         style={{ zIndex: 999999 }}
       />
      <RouterProvider router={router} />
    </QueryProvider>
  );
}