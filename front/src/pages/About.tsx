
import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Leaf, Brain, Globe, Users, Award, TrendingUp } from "lucide-react";
import { api } from "@/services/api";

interface AboutMetrics {
  crops_analyzed: number;
  active_users: number;
  success_rate: number;
  countries_served: number;
}

const About = () => {
  const [metrics, setMetrics] = useState<AboutMetrics>({
    crops_analyzed: 0,
    active_users: 0,
    success_rate: 0,
    countries_served: 0
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchAboutMetrics();
  }, []);

  const fetchAboutMetrics = async () => {
    setIsLoading(true);
    try {
      const response = await api.getAboutMetrics();
      setMetrics(response);
    } catch (error) {
      console.error('Error fetching about metrics:', error);
      // Keep default values if API fails
    } finally {
      setIsLoading(false);
    }
  };

  const features = [
    {
      icon: Brain,
      title: "Inteligencia Artificial Avanzada",
      description: "Algoritmos de machine learning entrenados con datos de más de 2,200 cultivos."
    },
    {
      icon: Globe,
      title: "Cobertura Regional",
      description: "Optimizado para condiciones específicas de suelo y clima."
    },
    {
      icon: Users,
      title: "Interfaz Intuitiva",
      description: "Diseñado para agricultores de todos los niveles técnicos con resultados fáciles de interpretar."
    },
    {
      icon: Award,
      title: "Precisión Comprobada",
      description: "97.8% de precisión en recomendaciones."
    }
  ];

  const technologies = [
    "React.js + Tailwind CSS", "Node.js + Express", "PostgreSQL", "Python + scikit-learn + torch", 
    "OpenStack instances + Nginx"
  ];

  const metricsDisplay = [
    { 
      label: "Cultivos Analizados", 
      value: isLoading ? "..." : metrics.crops_analyzed.toString(), 
      icon: Leaf 
    },
    { 
      label: "Usuarios Activos", 
      value: isLoading ? "..." : metrics.active_users.toLocaleString(), 
      icon: Users 
    },
    { 
      label: "Predicciones Exitosas", 
      value: isLoading ? "..." : `${metrics.success_rate}%`, 
      icon: TrendingUp 
    },
    { 
      label: "Países Atendidos", 
      value: isLoading ? "..." : metrics.countries_served.toString(), 
      icon: Globe 
    }
  ];

  return (
    <div className="min-h-screen py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Acerca de{" "}
            <span className="bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent">
              AgriAI Platform
            </span>
          </h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            Revolucionamos la agricultura con inteligencia artificial, proporcionando 
            recomendaciones precisas de cultivos para maximizar la productividad y sostenibilidad.
          </p>
        </div>

        {/* Mission Statement */}
        <Card className="border-green-100 mb-12">
          <CardContent className="p-8">
            <div className="text-center">
              <h2 className="text-2xl font-bold text-gray-900 mb-4">Nuestra Misión</h2>
              <p className="text-lg text-gray-700 max-w-4xl mx-auto leading-relaxed">
                Democratizar el acceso a tecnología agrícola avanzada mediante inteligencia artificial, 
                ayudando a agricultores de Latinoamérica a tomar decisiones informadas que mejoren 
                sus rendimientos, reduzcan riesgos y promuevan prácticas sostenibles.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-12">
          {metricsDisplay.map((metric, index) => (
            <Card key={index} className="border-green-100 text-center hover:shadow-lg transition-shadow">
              <CardContent className="p-6">
                <metric.icon className="h-8 w-8 text-green-600 mx-auto mb-3" />
                <div className="text-3xl font-bold text-gray-900 mb-1">{metric.value}</div>
                <p className="text-sm text-gray-600">{metric.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Features */}
        <div className="mb-12">
          <h2 className="text-3xl font-bold text-gray-900 text-center mb-8">
            Características Principales
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {features.map((feature, index) => (
              <Card key={index} className="border-green-100 hover:shadow-lg transition-shadow">
                <CardHeader>
                  <CardTitle className="flex items-center space-x-3">
                    <div className="p-2 bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg">
                      <feature.icon className="h-5 w-5 text-white" />
                    </div>
                    <span className="text-lg">{feature.title}</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-600">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Technology Stack */}
        <Card className="border-green-100 mb-12">
          <CardHeader>
            <CardTitle className="text-2xl font-bold text-gray-900 text-center">
              Stack Tecnológico
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-gray-600 text-center mb-6">
              Construido con las mejores tecnologías para garantizar escalabilidad, 
              precisión y rendimiento.
            </p>
            <div className="flex flex-wrap gap-2 justify-center">
              {technologies.map((tech, index) => (
                <Badge 
                  key={index} 
                  variant="outline" 
                  className="px-3 py-1 border-green-200 text-green-700 hover:bg-green-50"
                >
                  {tech}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* How It Works */}
        <Card className="border-green-100 mb-12">
          <CardHeader>
            <CardTitle className="text-2xl font-bold text-gray-900 text-center">
              ¿Cómo Funciona?
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="text-center">
                <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-full flex items-center justify-center mx-auto mb-4">
                  <span className="text-white font-bold text-xl">1</span>
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Análisis de Datos</h3>
                <p className="text-gray-600">
                  Recopilamos información sobre tipo de suelo, clima, región y área de cultivo.
                </p>
              </div>
              
              <div className="text-center">
                <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4">
                  <span className="text-white font-bold text-xl">2</span>
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Procesamiento IA</h3>
                <p className="text-gray-600">
                  Nuestros algoritmos analizan los datos.
                </p>
              </div>
              
              <div className="text-center">
                <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-600 rounded-full flex items-center justify-center mx-auto mb-4">
                  <span className="text-white font-bold text-xl">3</span>
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Recomendaciones</h3>
                <p className="text-gray-600">
                  Entregamos recomendaciones personalizadas con niveles de confianza y rentabilidad.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Contact CTA */}
        <Card className="border-green-100 bg-gradient-to-r from-green-600 to-emerald-600 text-white">
          <CardContent className="p-8 text-center">
            <h2 className="text-3xl font-bold mb-4">¿Listo para Empezar?</h2>
            <p className="text-green-100 mb-6 max-w-2xl mx-auto">
              Únete a miles de agricultores que ya están optimizando sus cultivos 
              con nuestras recomendaciones basadas en IA.
            </p>
            <div className="space-y-2">
              <p className="text-green-100">
                <strong>Contacto:</strong> holenderian@gmail.com | +52 55 4790 3290
              </p>
              <p className="text-green-100">
                <strong>Ubicación:</strong> Tec de Monterrey, CSF
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default About;
