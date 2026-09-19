import { RouterProvider } from "react-router-dom";
import { router } from "./app/router";
import { QueryProvider } from "./app/providers/QueryProvider";
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

export default function App() {
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