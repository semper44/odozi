import { useState } from 'react'
import { RouterProvider } from "react-router-dom";
import { router } from "./app/router";
import { QueryProvider } from "./app/providers/QueryProvider";
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

export default function App() {
  return (
    <QueryProvider>
       <ToastContainer aria-label="System Notifications" />
      <RouterProvider router={router} />
    </QueryProvider>
  );
}