// src/app/router/index.tsx

import { createBrowserRouter } from "react-router-dom";

import Home from "@/pages/Home";
import {GitHubLoginOrRegister} from "@/pages/registrationorlogin";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Home />,
  },
  {
    path: "/login",
    element: <GitHubLoginOrRegister />,
  },
 
]);