import { useState } from 'react'
import { RouterProvider } from "react-router-dom";
import { router } from "./app/router";
import { QueryProvider } from "./app/providers/QueryProvider";

export default function App() {
  return (
    <QueryProvider>
      <RouterProvider router={router} />
    </QueryProvider>
  );
}