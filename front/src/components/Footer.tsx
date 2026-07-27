
import { Leaf, Mail, Phone, MapPin } from "lucide-react";
import { Link } from "react-router-dom";

export const Footer = () => {
  return (
    <footer className="bg-gradient-to-r from-green-800 to-emerald-900 text-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Logo y descripción */}
          <div className="col-span-1 md:col-span-2">
            <div className="flex items-center space-x-3 mb-4">
              <div className="p-2 bg-gradient-to-br from-green-400 to-emerald-500 rounded-xl">
                <Leaf className="h-6 w-6 text-white" />
              </div>
              <div>
                <h3 className="text-xl font-bold">AgriAI Platform</h3>
                <p className="text-green-200 text-sm">Recomendación Inteligente de Cultivos</p>
              </div>
            </div>
            <p className="text-green-100 max-w-md">
              Transformamos la agricultura con inteligencia artificial, proporcionando recomendaciones 
              precisas de cultivos basadas en análisis de suelo, clima y condiciones regionales.
            </p>
          </div>

          {/* Enlaces */}
          <div>
            <h4 className="font-semibold mb-4 text-green-200">Plataforma</h4>
            <ul className="space-y-2">
              <li>
                <Link to="/dashboard" className="text-green-100 hover:text-white transition-colors">
                  Dashboard
                </Link>
              </li>
              <li>
                <Link to="/recommendations" className="text-green-100 hover:text-white transition-colors">
                  Recomendaciones
                </Link>
              </li>
              <li>
                <Link to="/analytics" className="text-green-100 hover:text-white transition-colors">
                  Analítica
                </Link>
              </li>
              <li>
                <Link to="/about" className="text-green-100 hover:text-white transition-colors">
                  Acerca de
                </Link>
              </li>
            </ul>
          </div>

          {/* Contacto */}
          <div>
            <h4 className="font-semibold mb-4 text-green-200">Contacto</h4>
            <ul className="space-y-2">
              <li className="flex items-center space-x-2">
                <Mail className="h-4 w-4 text-green-300" />
                <span className="text-green-100">holenderian@gmail.com</span>
              </li>
              <li className="flex items-center space-x-2">
                <Phone className="h-4 w-4 text-green-300" />
                <span className="text-green-100">+52 55 4790 3290</span>
              </li>
              <li className="flex items-center space-x-2">
                <MapPin className="h-4 w-4 text-green-300" />
                <span className="text-green-100">Tec de Monterrey, CSF</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="border-t border-green-700 mt-8 pt-6 text-center">
          <p className="text-green-200">
            © 2025 Ciscos. Todos los derechos reservados.
          </p>
        </div>
      </div>
    </footer>
  );
};
